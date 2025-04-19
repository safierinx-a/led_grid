defmodule Legrid.Controller.FrameBuffer do
  @moduledoc """
  A buffer for managing LED frames to be sent to controllers, implementing
  a pull-based delivery mechanism where controllers request frames in batches.

  Features:
  - Buffering of frames with priority handling
  - Batch processing of frame requests
  - Sequence tracking to ensure frame delivery
  - Automatic flushing of frames based on configurable thresholds
  """

  use GenServer
  require Logger

  # Configuration defaults
  @default_batch_size 30          # Default number of frames to send in a batch
  @default_priority_batch_size 20 # Max number of priority frames in a batch
  @default_max_delay 500          # Max delay in ms before forcing a flush
  @default_min_frames 10          # Min frames needed before auto-flushing
  @default_min_request_interval 50 # Min ms between requests from same controller

  # Client API

  @doc """
  Starts the frame buffer server with the given options
  """
  def start_link(opts \\ []) do
    name = Keyword.get(opts, :name, __MODULE__)
    GenServer.start_link(__MODULE__, opts, name: name)
  end

  @doc """
  Add a frame to the buffer to be sent to controllers

  Options:
  - priority: true if this frame should be prioritized (default: false)
  - pattern_id: ID of the pattern this frame belongs to (default: 0)
  """
  def add_frame(frame, opts \\ []) do
    priority = Keyword.get(opts, :priority, false)
    pattern_id = Keyword.get(opts, :pattern_id, 0)
    GenServer.cast(__MODULE__, {:add_frame, frame, priority, pattern_id})
  end

  @doc """
  Handle a batch request from a controller. Sends frames to the controller
  if any are available and the request is valid.

  Parameters:
  - controller_id: Unique ID of the requesting controller
  - last_sequence: Last sequence number received by the controller
  - space_available: Number of frame slots available on the controller
  - urgent: Whether this is an urgent request (controller needs frames immediately)
  """
  def handle_batch_request(controller_id, last_sequence, space_available, urgent \\ false) do
    GenServer.cast(__MODULE__, {:batch_request, controller_id, last_sequence, space_available, urgent})
  end

  @doc """
  Flush all buffered frames to controllers with pending requests
  """
  def flush do
    GenServer.cast(__MODULE__, :flush)
  end

  @doc """
  Get current status of the frame buffer
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  # Server callbacks

  @impl true
  def init(opts) do
    batch_size = Keyword.get(opts, :batch_size, @default_batch_size)
    priority_batch_size = Keyword.get(opts, :priority_batch_size, @default_priority_batch_size)
    max_delay = Keyword.get(opts, :max_delay, @default_max_delay)
    min_frames = Keyword.get(opts, :min_frames, @default_min_frames)

    # Start timer for automatic flushing
    schedule_flush(max_delay)

    # Initialize state
    state = %{
      # Frames storage
      priority_frames: [],     # List of priority frames awaiting sending
      regular_frames: [],      # List of regular frames awaiting sending

      # Sequence tracking - highest sequence sent to each controller
      sequences: %{},          # Map of controller_id -> last_sequence

      # Controller requests tracking
      pending_requests: %{},   # Map of controller_id -> {last_sequence, space_available, timestamp}

      # Current pattern ID
      current_pattern_id: 0,

      # Configuration
      batch_size: batch_size,
      priority_batch_size: priority_batch_size,
      max_delay: max_delay,
      min_frames: min_frames,
      min_request_interval: @default_min_request_interval
    }

    {:ok, state}
  end

  @impl true
  def handle_cast({:add_frame, frame, priority, pattern_id}, state) do
    # Add frame to appropriate queue
    new_state = if priority do
      %{state |
        priority_frames: state.priority_frames ++ [%{frame: frame, pattern_id: pattern_id}],
        current_pattern_id: pattern_id
      }
    else
      %{state |
        regular_frames: state.regular_frames ++ [%{frame: frame, pattern_id: pattern_id}],
        current_pattern_id: pattern_id
      }
    end

    # Check if we should flush based on number of frames
    total_frames = length(new_state.priority_frames) + length(new_state.regular_frames)

    new_state =
      if total_frames >= state.min_frames && map_size(state.pending_requests) > 0 do
        do_flush_to_all_controllers(new_state)
      else
        new_state
      end

    {:noreply, new_state}
  end

  @impl true
  def handle_cast({:batch_request, controller_id, last_sequence, space_available, urgent}, state) do
    now = System.system_time(:millisecond)

    # Check if this is a valid request (not too soon after previous request)
    is_valid_request = case Map.get(state.pending_requests, controller_id) do
      nil -> true  # First request from this controller
      {_, _, timestamp} ->
        now - timestamp >= state.min_request_interval
    end

    if is_valid_request do
      # Update pending request
      state = %{state |
        pending_requests: Map.put(state.pending_requests, controller_id, {last_sequence, space_available, now})
      }

      # If urgent or we have enough frames, send immediately
      has_enough_frames = length(state.priority_frames) + length(state.regular_frames) >= state.min_frames

      state =
        if urgent || has_enough_frames do
          do_check_pending_requests(state, controller_id)
        else
          state
        end

      {:noreply, state}
    else
      # Request too soon after previous one, ignore
      {:noreply, state}
    end
  end

  @impl true
  def handle_cast(:flush, state) do
    # Only flush if we have pending requests
    new_state = if map_size(state.pending_requests) > 0 do
      do_flush_to_all_controllers(state)
    else
      state
    end

    # Reschedule the flush timer
    schedule_flush(new_state.max_delay)

    {:noreply, new_state}
  end

  @impl true
  def handle_info(:flush_timer, state) do
    # Check if we have any frames to flush
    has_frames = length(state.priority_frames) + length(state.regular_frames) > 0

    # Only flush if we have frames and pending requests
    new_state = if has_frames && map_size(state.pending_requests) > 0 do
      do_flush_to_all_controllers(state)
    else
      state
    end

    # Reschedule the flush timer
    schedule_flush(new_state.max_delay)

    {:noreply, new_state}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      priority_frames: length(state.priority_frames),
      regular_frames: length(state.regular_frames),
      pending_requests: map_size(state.pending_requests),
      current_pattern_id: state.current_pattern_id
    }

    {:reply, status, state}
  end

  # Private functions

  # Check if we have a pending request from a specific controller and send frames if needed
  defp do_check_pending_requests(state, controller_id) do
    case Map.get(state.pending_requests, controller_id) do
      nil ->
        # No pending request for this controller
        state

      {last_sequence, space_available, _timestamp} ->
        # Get the sequence number for this controller
        current_sequence = Map.get(state.sequences, controller_id, 0)

        # Only send if the controller is up to date with sequences
        if last_sequence >= current_sequence do
          # Prepare batch
          {batch, remaining_priority, remaining_regular} = prepare_batch(
            state.priority_frames,
            state.regular_frames,
            space_available,
            state.priority_batch_size,
            state.batch_size
          )

          if length(batch) > 0 do
            # Update sequence
            new_sequence = current_sequence + 1

            # Send batch to controller
            send_batch_to_controller(
              controller_id,
              batch,
              new_sequence,
              state.current_pattern_id
            )

            # Update state
            %{state |
              priority_frames: remaining_priority,
              regular_frames: remaining_regular,
              sequences: Map.put(state.sequences, controller_id, new_sequence),
              pending_requests: Map.delete(state.pending_requests, controller_id)
            }
          else
            # No frames to send
            state
          end
        else
          # Controller is behind, don't send
          state
        end
    end
  end

  # Flush frames to all controllers with pending requests
  defp do_flush_to_all_controllers(state) do
    # Process each controller with a pending request
    Enum.reduce(Map.keys(state.pending_requests), state, fn controller_id, acc_state ->
      do_check_pending_requests(acc_state, controller_id)
    end)
  end

  # Prepare a batch of frames to send, considering priority frames first
  defp prepare_batch(priority_frames, regular_frames, space_available, priority_limit, batch_limit) do
    # Calculate how many frames to send
    batch_size = min(space_available, batch_limit)

    # Priority frames get sent first, up to the priority limit
    priority_count = min(length(priority_frames), min(batch_size, priority_limit))

    # Regular frames fill the remaining space
    regular_count = min(length(regular_frames), batch_size - priority_count)

    # Split the priority frames
    {priority_batch, remaining_priority} = Enum.split(priority_frames, priority_count)

    # Split the regular frames
    {regular_batch, remaining_regular} = Enum.split(regular_frames, regular_count)

    # Combine the batches
    batch = priority_batch ++ regular_batch

    {batch, remaining_priority, remaining_regular}
  end

  # Send a batch of frames to a controller
  defp send_batch_to_controller(controller_id, batch, sequence, pattern_id) do
    # Extract frames and check if any are priority
    frames = Enum.map(batch, &(&1.frame))
    has_priority = Enum.any?(batch, &(&1[:priority] == true))

    # Get timestamp
    timestamp = System.system_time(:millisecond)

    # Broadcast the batch to the controller
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:socket",
      {:controller_batch, controller_id, frames, has_priority, pattern_id, sequence, timestamp}
    )

    Logger.debug("Sent batch to controller #{controller_id}: #{length(frames)} frames, seq=#{sequence}")
  end

  # Schedule the next automatic flush
  defp schedule_flush(delay) do
    Process.send_after(self(), :flush_timer, delay)
  end
end
