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
    GenServer.call(__MODULE__, {:start_pattern, pattern_id, params, opts})
  end

  @doc """
  Updates the parameters of the currently running pattern.

  - params: Map of parameters to pass to the pattern generator
  """
  def update_pattern_params(params) do
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
  def init(_opts) do
    state = %{
      current_pattern: nil,
      module: nil,
      state: nil,
      last_frame_time: nil,
      timer_ref: nil,
      fps: @default_fps,
      frame_interval: trunc(1000 / @default_fps),
      subscribers: []
    }

    {:ok, state}
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
      {:reply, {:ok, %{
        id: state.current_pattern,
        fps: state.fps
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
end
