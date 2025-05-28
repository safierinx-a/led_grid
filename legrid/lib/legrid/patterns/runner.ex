defmodule Legrid.Patterns.Runner do
  @moduledoc """
  Manages the execution of pattern generators.

  This module is responsible for:
  - Starting and stopping pattern generators
  - Requesting frames at the appropriate intervals
  - Publishing frames to subscribers
  """

  use GenServer

  alias Legrid.Frame
  alias Legrid.Patterns.Registry

  # Default frame rate in frames per second
  @default_fps 30

  # How often to check for rate limiting updates
  @rate_limit_check_interval 50  # ms (reduced from 100ms for faster response)
  # Maximum updates to process per interval
  @max_updates_per_interval 10   # Increased from 5 for faster response

  # Client API

  @doc """
  Starts the pattern runner.
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Starts a pattern generator with the given parameters.

  - pattern_id: ID of the pattern to start
  - params: Map of parameters to pass to the pattern generator
  - opts: Additional options like FPS
  """
  def start_pattern(pattern_id, params \\ %{}, opts \\ []) do
    # First, send an immediate clear display command to all controllers
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:clear_display, true})

    # Small delay to ensure clear command is processed
    Process.sleep(50)

    # Then start the pattern
    GenServer.call(__MODULE__, {:start_pattern, pattern_id, params, opts})
  end

  @doc """
  Updates the parameters of the currently running pattern.

  - params: Map of parameters to pass to the pattern generator
  """
  def update_pattern_params(params) do
    # First, send a parameter change notification to all controllers
    # This ensures clean transitions when parameters change significantly
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:parameter_change, params})

    # Small delay to ensure parameter change command is processed
    Process.sleep(50)

    # Then update the parameters
    GenServer.call(__MODULE__, {:update_params, params})
  end

  @doc """
  Sends a blank frame to clear all LEDs.
  """
  def clear_frame do
    GenServer.call(__MODULE__, :clear_frame)
  end

  @doc """
  Stops the currently running pattern generator.
  """
  def stop_pattern do
    GenServer.call(__MODULE__, :stop_pattern)
  end

  @doc """
  Returns information about the currently running pattern.
  """
  def current_pattern do
    GenServer.call(__MODULE__, :current_pattern)
  end

  @doc """
  Subscribes to frame updates.

  The caller will receive messages of the form:
  {:frame, frame}
  """
  def subscribe do
    Phoenix.PubSub.subscribe(Legrid.PubSub, "frames")
  end

  # Server callbacks

  @impl true
  def init(_) do
    state = %{
      current_pattern: nil,
      module: nil,
      state: nil,
      timer_ref: nil,
      last_frame_time: nil,
      fps: @default_fps,
      frame_interval: trunc(1000 / @default_fps),
      # Rate limiting state
      update_queue: :queue.new(),
      last_rate_check: System.monotonic_time(:millisecond),
      updates_in_interval: 0,
      rate_check_timer: nil
    }

    # Start the rate limit checker
    rate_check_timer = schedule_rate_limit_check()

    {:ok, %{state | rate_check_timer: rate_check_timer}}
  end

  @impl true
  def handle_call({:start_pattern, pattern_id, params, opts}, _from, state) do
    # Stop any current pattern
    state = stop_current_pattern(state)

    # Get the pattern module
    case Registry.get_pattern(pattern_id) do
      {:error, _} = error ->
        {:reply, error, state}

      {:ok, metadata} ->
        # Get the module from the registry state
        registry_state = :sys.get_state(Registry)
        module = registry_state.patterns[pattern_id]

        fps = Keyword.get(opts, :fps, @default_fps)
        frame_interval = trunc(1000 / fps)

        case module.init(params) do
          {:error, _} = error ->
            {:reply, error, state}

          {:ok, pattern_state} ->
            # Send a blank frame BEFORE scheduling the next frame
            blank_frame = %Frame{
              id: UUID.uuid4(),
              pixels: create_blank_pixels(600),
              timestamp: System.system_time(:millisecond),
              source: "blank",
              width: 25,
              height: 24,
              metadata: %{"pattern_id" => pattern_id, "priority" => true}
            }

            # Send the blank frame to clear the display immediately
            Phoenix.PubSub.broadcast(Legrid.PubSub, "frames", {:frame, blank_frame})

            # Schedule the first frame
            timer_ref = schedule_next_frame(0)

            new_state = %{
              state |
              current_pattern: pattern_id,
              module: module,
              state: pattern_state,
              last_frame_time: System.monotonic_time(:millisecond),
              timer_ref: timer_ref,
              fps: fps,
              frame_interval: frame_interval
            }

            # Ensure we flush the FrameBuffer when a pattern changes
            try do
              Legrid.Controller.FrameBuffer.flush()
            rescue
              _ -> :ok # Ignore errors if FrameBuffer is not available
            end

            # Extract only essential parameters for the UI update
            ui_params = extract_ui_params(params)

            # Broadcast pattern change to all clients
            Phoenix.PubSub.broadcast(
              Legrid.PubSub,
              "pattern_updates",
              {:pattern_changed, pattern_id, ui_params}
            )

            {:reply, :ok, new_state}
        end
    end
  end

  @impl true
  def handle_call({:update_params, params}, _from, state) do
    if state.current_pattern && state.module && state.state do
      # Check if the module supports parameter updates
      if function_exported?(state.module, :update_params, 2) do
        case state.module.update_params(state.state, params) do
          {:ok, new_state} ->
            # Increment parameter version to track significant changes
            try do
              Legrid.Controller.FrameBuffer.increment_parameter_version()
            rescue
              _ -> :ok # Ignore errors if FrameBuffer is not available
            end

            # Ensure we flush the FrameBuffer when parameters change
            try do
              Legrid.Controller.FrameBuffer.flush()
            rescue
              _ -> :ok # Ignore errors if FrameBuffer is not available
            end

            {:reply, :ok, %{state | state: new_state}}

          {:error, _} = error ->
            {:reply, error, state}
        end
      else
        # If the module doesn't support parameter updates, restart the pattern
        # with the new parameters
        {:reply, :ok, state}
      end
    else
      {:reply, {:error, :no_pattern_running}, state}
    end
  end

  @impl true
  def handle_call(:clear_frame, _from, state) do
    # Create a blank frame
    blank_frame = %Frame{
      pixels: create_blank_pixels(600),
      timestamp: System.system_time(:millisecond)
    }

    # Broadcast the blank frame
    Phoenix.PubSub.broadcast(Legrid.PubSub, "frames", {:frame, blank_frame})

    {:reply, :ok, state}
  end

  @impl true
  def handle_call(:stop_pattern, _from, state) do
    new_state = stop_current_pattern(state)
    {:reply, :ok, new_state}
  end

  @impl true
  def handle_call(:current_pattern, _from, state) do
    if state.current_pattern do
      # Get the pattern parameters from the state if available
      pattern_params = if state.state do
        # Extract common parameters that might be preserved
        global_params = ["brightness", "color_scheme", "speed"]

        # Safely extract parameters from state regardless of whether it's a struct or a map
        params = cond do
          # If it's a struct, use Map.from_struct
          is_struct(state.state) ->
            state.state
            |> Map.from_struct()

          # If it's a map but not a struct, use directly
          is_map(state.state) ->
            state.state

          # Fallback for other cases
          true ->
            %{}
        end

        # Extract common parameters
        params
        |> Enum.filter(fn {key, _val} ->
          Enum.member?(global_params, to_string(key))
        end)
        |> Enum.map(fn {key, val} -> {to_string(key), val} end)
        |> Enum.into(%{})
      else
        %{}
      end

      {:reply, {:ok, %{
        id: state.current_pattern,
        fps: state.fps,
        params: extract_ui_params(pattern_params)
      }}, state}
    else
      {:reply, {:error, :no_pattern_running}, state}
    end
  end

  @impl true
  def handle_info(:generate_frame, state) do
    now = System.monotonic_time(:millisecond)
    elapsed = now - state.last_frame_time

    case state.module.render(state.state, elapsed) do
      {:error, reason} ->
        IO.puts("Error generating frame: #{reason}")
        # Schedule the next frame anyway
        timer_ref = schedule_next_frame(state.frame_interval)
        {:noreply, %{state | timer_ref: timer_ref, last_frame_time: now}}

      {:ok, frame, new_pattern_state} ->
        # Add pattern ID to frame metadata if not already present
        frame = if frame.metadata && Map.has_key?(frame.metadata, "pattern_id") do
          frame
        else
          # Create or update metadata with pattern ID
          metadata = (frame.metadata || %{}) |> Map.put("pattern_id", state.current_pattern)
          %{frame | metadata: metadata}
        end

        # Publish the frame
        Phoenix.PubSub.broadcast(Legrid.PubSub, "frames", {:frame, frame})

        # Schedule the next frame
        timer_ref = schedule_next_frame(state.frame_interval)

        {:noreply, %{state |
          state: new_pattern_state,
          timer_ref: timer_ref,
          last_frame_time: now
        }}
    end
  end

  # Schedule the rate limit check
  defp schedule_rate_limit_check do
    Process.send_after(self(), :process_update_queue, @rate_limit_check_interval)
  end

  # Process the update queue at regular intervals to prevent flooding
  @impl true
  def handle_info(:process_update_queue, state) do
    now = System.monotonic_time(:millisecond)

    # Reset counter if we're in a new interval
    state = if now - state.last_rate_check >= @rate_limit_check_interval do
      %{state | last_rate_check: now, updates_in_interval: 0}
    else
      state
    end

    # Process up to max_updates_per_interval from the queue
    {new_state, queue_empty} = process_queued_updates(state, @max_updates_per_interval)

    # Schedule next check if needed
    rate_check_timer = if queue_empty do
      # Only check periodically if queue is empty
      schedule_rate_limit_check()
    else
      # Check more frequently if we still have items
      Process.send_after(self(), :process_update_queue, @rate_limit_check_interval)
    end

    {:noreply, %{new_state | rate_check_timer: rate_check_timer}}
  end

  # Process a batch of updates from the queue
  defp process_queued_updates(state, max_updates) do
    process_queued_updates(state, max_updates, queue_empty: :queue.is_empty(state.update_queue))
  end

  defp process_queued_updates(state, _, queue_empty: true), do: {state, true}
  defp process_queued_updates(state, 0, _), do: {state, false}
  defp process_queued_updates(state, max_updates, _) do
    case :queue.out(state.update_queue) do
      {{:value, params}, new_queue} ->
        # Apply the parameter update
        new_state = apply_param_update(state, params)
        # Continue processing the queue
        process_queued_updates(
          %{new_state | update_queue: new_queue, updates_in_interval: state.updates_in_interval + 1},
          max_updates - 1
        )

      {:empty, _} ->
        {state, true}
    end
  end

  # Apply a parameter update to the pattern
  defp apply_param_update(state, params) do
    if state.current_pattern && state.module && state.state &&
       function_exported?(state.module, :update_params, 2) do

      case state.module.update_params(state.state, params) do
        {:ok, new_state} ->
          # Generate frame with updated parameters
          try do
            case state.module.render(new_state, 0) do
              {:ok, frame, _} ->
                # Send frame immediately
                frame = ensure_pattern_id_in_metadata(frame, state.current_pattern)
                Phoenix.PubSub.broadcast(Legrid.PubSub, "frames", {:frame, frame})
              _ -> :ok
            end
          rescue
            _ -> :ok
          end

          # Flush FrameBuffer
          try do
            Legrid.Controller.FrameBuffer.flush()
          rescue
            _ -> :ok
          end

          # Extract UI params and broadcast change
          ui_params = extract_ui_params(params)
          Phoenix.PubSub.broadcast(
            Legrid.PubSub,
            "pattern_updates",
            {:pattern_changed, state.current_pattern, ui_params}
          )

          %{state | state: new_state}

        {:error, _} ->
          state
      end
    else
      state
    end
  end

  # Ensure pattern ID is in frame metadata
  defp ensure_pattern_id_in_metadata(frame, pattern_id) do
    if frame.metadata && Map.has_key?(frame.metadata, "pattern_id") do
      frame
    else
      metadata = (frame.metadata || %{}) |> Map.put("pattern_id", pattern_id)
      %{frame | metadata: metadata}
    end
  end

  # Helper functions

  defp stop_current_pattern(state) do
    # Cancel any pending frame generation
    if state.timer_ref, do: Process.cancel_timer(state.timer_ref)

    # Terminate the current pattern if one is running
    if state.current_pattern && state.module && state.state do
      if function_exported?(state.module, :terminate, 1) do
        state.module.terminate(state.state)
      end
    end

    %{state |
      current_pattern: nil,
      module: nil,
      state: nil,
      last_frame_time: nil,
      timer_ref: nil
    }
  end

  defp schedule_next_frame(interval) do
    Process.send_after(self(), :generate_frame, interval)
  end

  defp create_blank_pixels(count) do
    for _i <- 1..count, do: {0, 0, 0}
  end

  # Extract only essential parameters for UI updates
  defp extract_ui_params(params) when is_map(params) do
    # Common parameters that are safe to broadcast
    common_keys = [
      "brightness", "color_scheme", "speed",
      "contrast", "density", "scale", "frequency",
      "amplitude", "illusion_type", "sprite_type", "fill_style"
    ]

    # Filter out non-essential params and any large data structures
    try do
      params
      |> Enum.filter(fn {key, value} ->
           is_binary(key) && Enum.member?(common_keys, key) &&
           (is_binary(value) || is_number(value) || is_boolean(value) || is_atom(value))
         end)
      |> Enum.into(%{})
    rescue
      _ -> %{} # Return empty map if we encounter any errors
    end
  end
  defp extract_ui_params(_), do: %{}
end
