defmodule Legrid.Controller.FrameBuffer do
  @moduledoc """
  Frame buffering system for batch transmission to controllers.

  This module collects frames and sends them in batches to improve
  connection stability and efficiency with LED controllers.

  Features:
  - Collects frames into batches
  - Automatically flushes based on batch size or timeout
  - Prioritizes pattern changes
  - Optimizes bandwidth usage
  """

  use GenServer
  require Logger

  @topic "controller:interface"
  @default_batch_size 60
  @default_priority_batch_size 120
  @default_max_delay 100
  @default_min_frames 20
  @default_min_request_interval 50

  # Client API

  @doc """
  Starts the frame buffer.

  Options:
  - batch_size: Maximum frames per batch (default: 60)
  - priority_batch_size: Maximum frames per priority batch (default: 120)
  - max_delay: Maximum delay in ms before sending a partial batch (default: 100)
  - min_frames: Minimum frames before sending a partial batch (default: 20)
  - min_request_interval: Minimum ms between batch sends to same controller (default: 50)
  """
  def start_link(opts \\ []) do
    name = Keyword.get(opts, :name, __MODULE__)
    GenServer.start_link(__MODULE__, opts, name: name)
  end

  @doc """
  Add a frame to the buffer.

  Options:
  - priority: Whether this is a priority frame (pattern change, etc.)
  - pattern_id: ID of the pattern generating this frame
  """
  def add_frame(frame, opts \\ []) do
    priority = Keyword.get(opts, :priority, false)
    pattern_id = Keyword.get(opts, :pattern_id, nil)
    GenServer.cast(__MODULE__, {:add_frame, frame, priority, pattern_id})
  end

  @doc """
  Handle a batch request from a controller
  """
  def handle_batch_request(controller_id, last_sequence, space_available, urgent) do
    GenServer.cast(__MODULE__, {:batch_request, controller_id, last_sequence, space_available, urgent})
  end

  @doc """
  Immediately flush the buffer.
  """
  def flush do
    GenServer.cast(__MODULE__, :flush)
  end

  @doc """
  Get buffer status.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  @doc """
  Signal that a controller is ready for more frames
  """
  def controller_ready(controller_id, sequence, buffer_fullness, buffer_capacity) do
    GenServer.cast(__MODULE__, {:controller_ready, controller_id, sequence, buffer_fullness, buffer_capacity})
  end

  @doc """
  Increment the parameter version counter.
  Called when pattern parameters change significantly.
  """
  def increment_parameter_version do
    GenServer.call(__MODULE__, :increment_parameter_version)
  end

  # Server callbacks

  @impl true
  def init(opts) do
    Phoenix.PubSub.subscribe(Legrid.PubSub, @topic)

    batch_size = Keyword.get(opts, :batch_size, @default_batch_size)
    priority_batch_size = Keyword.get(opts, :priority_batch_size, @default_priority_batch_size)
    max_delay = Keyword.get(opts, :max_delay, @default_max_delay)
    min_frames = Keyword.get(opts, :min_frames, @default_min_frames)
    min_request_interval = Keyword.get(opts, :min_request_interval, @default_min_request_interval)

    initial_state = %{
      frames: [],
      pending_requests: %{},
      priority_frames: [],
      current_sequence: 0,
      current_pattern_id: nil,
      parameter_version: 1,  # Track parameter changes with version
      batch_size: batch_size,
      priority_batch_size: priority_batch_size,
      max_delay: max_delay,
      min_frames: min_frames,
      min_request_interval: min_request_interval,
      last_batch_time: nil
    }

    {:ok, initial_state}
  end

  @impl true
  def handle_cast({:add_frame, frame, priority, pattern_id}, state) do
    # Add parameter version to frame metadata
    frame = if frame.metadata do
      metadata = Map.put(frame.metadata, "parameter_version", state.parameter_version)
      %{frame | metadata: metadata}
    else
      %{frame | metadata: %{"parameter_version" => state.parameter_version}}
    end

    # Check if pattern has changed
    pattern_changed = state.current_pattern_id != nil &&
                      pattern_id != nil &&
                      pattern_id != state.current_pattern_id

    # Log pattern changes
    if pattern_changed do
      Logger.info("Pattern changed from #{state.current_pattern_id} to #{pattern_id}")
    end

    # Update state with new frame
    state =
      if priority || pattern_changed do
        # Add to priority frames
        %{state | priority_frames: [frame | state.priority_frames]}
      else
        # Add to regular frames
        %{state | frames: [frame | state.frames]}
      end
      |> Map.put(:current_pattern_id, pattern_id)

    # If pattern has changed, flush existing frames to all controllers
    state =
      if pattern_changed do
        Logger.debug("Pattern changed from #{state.current_pattern_id} to #{pattern_id}, flushing frames")

        # Instead of trying to use private Phoenix.PubSub function subscribers/2
        # we'll use the controllers we already know about from pending_requests

        # Notify controllers we know about from pending requests
        Enum.each(Map.keys(state.pending_requests), fn controller_id ->
          Logger.debug("Notifying controller #{controller_id} of pattern change")
          Process.send_after(self(), {:batch_requested, controller_id, 0, 60, true}, 50)
        end)

        # Broadcast a general notification about pattern change
        Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:pattern_changed, pattern_id})

        do_flush_to_all_controllers(state)
      else
        # Check if we have pending requests and enough frames or if urgent (priority)
        check_pending_requests(state, priority)
      end

    {:noreply, state}
  end

  @impl true
  def handle_cast({:batch_request, controller_id, last_sequence, space_available, urgent}, state) do
    # Record the request in our pending requests map with timestamp
    now = System.monotonic_time(:millisecond)

    # Log request details
    Logger.info("FrameBuffer: received batch request from controller #{controller_id}: seq=#{last_sequence}, space=#{space_available}, urgent=#{urgent}")
    Logger.debug("FrameBuffer state: #{length(state.frames)} regular frames, #{length(state.priority_frames)} priority frames, pattern=#{inspect(state.current_pattern_id)}")

    pending_requests = Map.put(state.pending_requests, controller_id, %{
      last_sequence: last_sequence,
      space_available: space_available,
      urgent: urgent,
      timestamp: now
    })

    state = %{state | pending_requests: pending_requests}

    # Check if we should immediately send a batch
    state =
      cond do
        # If urgent request and we have priority frames, send those immediately
        urgent && length(state.priority_frames) > 0 ->
          Logger.info("FrameBuffer: urgent request with priority frames, sending immediately to #{controller_id}")
          send_batch_to_controller(controller_id, state, true)

        # If we have enough regular frames, send those
        length(state.frames) >= min(state.min_frames, space_available) ->
          Logger.info("FrameBuffer: enough regular frames available, sending to #{controller_id}")
          send_batch_to_controller(controller_id, state, false)

        # Otherwise wait for more frames or until max_delay is reached
        true ->
          Logger.info("FrameBuffer: not enough frames yet, waiting for more before sending to #{controller_id}")
          state
      end

    {:noreply, state}
  end

  @impl true
  def handle_cast(:flush, state) do
    state = do_flush_to_all_controllers(state)
    {:noreply, state}
  end

  @impl true
  def handle_info({:batch_requested, controller_id, last_sequence, space_available, urgent}, state) do
    # Forward to our handle_batch_request function
    handle_batch_request(controller_id, last_sequence, space_available, urgent)
    {:noreply, state}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      frames_count: length(state.frames),
      priority_frames_count: length(state.priority_frames),
      pattern_id: state.current_pattern_id,
      current_sequence: state.current_sequence,
      pending_requests: Map.keys(state.pending_requests)
    }

    {:reply, status, state}
  end

  @impl true
  def handle_call(:increment_parameter_version, _from, state) do
    new_version = state.parameter_version + 1
    Logger.info("Incrementing parameter version to #{new_version}")
    {:reply, new_version, %{state | parameter_version: new_version}}
  end

  # Private functions

  defp check_pending_requests(state, is_priority) do
    now = System.monotonic_time(:millisecond)

    # If we have priority frames and priority request, send immediately
    if is_priority && length(state.priority_frames) > 0 do
      # Send priority batch to all pending controllers
      Enum.reduce(state.pending_requests, state, fn {controller_id, _req}, acc_state ->
        send_batch_to_controller(controller_id, acc_state, true)
      end)
    else
      # For non-priority frames, check time-based conditions
      state.pending_requests
      |> Enum.reduce(state, fn {controller_id, request}, acc_state ->
        cond do
          # If max delay exceeded since last batch, send batch
          state.last_batch_time && (now - state.last_batch_time) > state.max_delay ->
            send_batch_to_controller(controller_id, acc_state, false)

          # If we have enough frames based on request's space_available, send batch
          length(acc_state.frames) >= min(acc_state.batch_size, request.space_available) ->
            send_batch_to_controller(controller_id, acc_state, false)

          # Otherwise keep waiting
          true ->
            acc_state
        end
      end)
    end
  end

  defp send_batch_to_controller(controller_id, state, is_priority) do
    # Get the request info
    request = Map.get(state.pending_requests, controller_id)

    if request do
      # Determine which frames to send and how many
      {frames, max_frames} =
        if is_priority do
          {state.priority_frames, min(state.priority_batch_size, request.space_available)}
        else
          {state.frames, min(state.batch_size, request.space_available)}
        end

      # Take the requested number of frames
      frames_to_send = frames
                      |> Enum.take(max_frames)
                      |> Enum.reverse()

      if length(frames_to_send) > 0 do
        # Prepare the batch
        sequence = state.current_sequence + 1
        timestamp = System.system_time(:millisecond)

        Logger.info("FrameBuffer: sending batch to controller #{controller_id}: #{length(frames_to_send)} frames, sequence #{sequence}, pattern #{inspect(state.current_pattern_id)}")

        # Log sample frame data
        if length(frames_to_send) > 0 do
          first_frame = List.first(frames_to_send)
          Logger.debug("FrameBuffer: first frame pixels: #{length(first_frame.pixels)}, metadata: #{inspect(first_frame.metadata)}")
        end

        # Broadcast the batch to the specific controller
        Phoenix.PubSub.broadcast(
          Legrid.PubSub,
          "controller:socket",
          {:controller_batch, controller_id, frames_to_send, is_priority, state.current_pattern_id, sequence, timestamp}
        )

        # Update state
        remaining_frames = Enum.drop(frames, max_frames)

        new_state =
          if is_priority do
            %{state |
              priority_frames: remaining_frames,
              current_sequence: sequence,
              last_batch_time: System.monotonic_time(:millisecond)
            }
          else
            %{state |
              frames: remaining_frames,
              current_sequence: sequence,
              last_batch_time: System.monotonic_time(:millisecond)
            }
          end

        # Remove this controller from pending requests
        %{new_state | pending_requests: Map.delete(new_state.pending_requests, controller_id)}
      else
        # No frames to send, leave state unchanged
        Logger.info("FrameBuffer: no frames to send to controller #{controller_id}")
        state
      end
    else
      # No request for this controller, leave state unchanged
      Logger.debug("FrameBuffer: no request found for controller #{controller_id}")
      state
    end
  end

  defp do_flush_to_all_controllers(state) do
    # Send all pending frames to all controllers with pending requests
    Enum.reduce(state.pending_requests, state, fn {controller_id, _req}, acc_state ->
      # First send any priority frames
      acc_state =
        if length(acc_state.priority_frames) > 0 do
          send_batch_to_controller(controller_id, acc_state, true)
        else
          acc_state
        end

      # Then send regular frames
      if length(acc_state.frames) > 0 do
        send_batch_to_controller(controller_id, acc_state, false)
      else
        acc_state
      end
    end)
  end
end
