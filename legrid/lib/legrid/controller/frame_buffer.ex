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

  @default_batch_size 120      # Default frames per batch
  @default_max_delay_ms 500    # Max delay before sending a partial batch
  @default_min_frames 5        # Min frames before sending a partial batch

  # Client API

  @doc """
  Starts the frame buffer.

  Options:
  - batch_size: Maximum frames per batch (default: 120)
  - max_delay: Maximum delay in ms before sending a partial batch (default: 500)
  - min_frames: Minimum frames before sending a partial batch (default: 5)
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Add a frame to the buffer.

  Options:
  - priority: Whether this is a priority frame (pattern change, etc.)
  - pattern_id: ID of the pattern generating this frame
  """
  def add_frame(frame, opts \\ []) do
    GenServer.cast(__MODULE__, {:add_frame, frame, opts})
  end

  @doc """
  Immediately flush the buffer.
  """
  def flush do
    GenServer.call(__MODULE__, :flush)
  end

  @doc """
  Get buffer status.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  # Server callbacks

  @impl true
  def init(opts) do
    batch_size = Keyword.get(opts, :batch_size, @default_batch_size)
    max_delay = Keyword.get(opts, :max_delay, @default_max_delay_ms)
    min_frames = Keyword.get(opts, :min_frames, @default_min_frames)

    # Set up timers to periodically check for partial batches
    schedule_check_flush()

    state = %{
      frames: [],
      current_pattern_id: nil,
      batch_size: batch_size,
      max_delay: max_delay,
      min_frames: min_frames,
      last_frame_time: System.monotonic_time(:millisecond),
      batches_sent: 0,
      frames_sent: 0
    }

    {:ok, state}
  end

  @impl true
  def handle_cast({:add_frame, frame, opts}, state) do
    # Extract options
    is_priority = Keyword.get(opts, :priority, false)
    pattern_id = Keyword.get(opts, :pattern_id, nil)

    # Check if this is a new pattern - needs priority flush
    pattern_changed = pattern_id != nil && state.current_pattern_id != nil &&
                     pattern_id != state.current_pattern_id

    # Handle priority frames and pattern changes
    state = cond do
      # For priority frames, flush existing buffer first
      is_priority && length(state.frames) > 0 ->
        # Flush current frames with current pattern
        do_flush(state)

      # For pattern changes, flush existing buffer as well
      pattern_changed && length(state.frames) > 0 ->
        # Flush current frames with current pattern
        do_flush(state)

      # Otherwise keep the current state
      true ->
        state
    end

    # Add this frame to buffer
    new_state = %{state |
      frames: state.frames ++ [frame],
      last_frame_time: System.monotonic_time(:millisecond),
      current_pattern_id: pattern_id || state.current_pattern_id
    }

    # Flush if we've reached the batch size
    if length(new_state.frames) >= new_state.batch_size do
      # Flush all frames
      {:noreply, do_flush(new_state, is_priority || pattern_changed)}
    else
      # Continue collecting frames
      {:noreply, new_state}
    end
  end

  @impl true
  def handle_call(:flush, _from, state) do
    new_state = do_flush(state)
    {:reply, :ok, new_state}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      frames_in_buffer: length(state.frames),
      batch_size: state.batch_size,
      batches_sent: state.batches_sent,
      frames_sent: state.frames_sent,
      current_pattern_id: state.current_pattern_id
    }

    {:reply, status, state}
  end

  @impl true
  def handle_info(:check_flush, state) do
    # Check if we should flush based on time
    now = System.monotonic_time(:millisecond)
    time_since_last_frame = now - state.last_frame_time

    # Flush if enough time has passed and we have at least the minimum number of frames
    state = if time_since_last_frame >= state.max_delay &&
               length(state.frames) >= state.min_frames do
      do_flush(state)
    else
      state
    end

    # Reschedule the check
    schedule_check_flush()

    {:noreply, state}
  end

  # Private functions

  defp do_flush(state, is_priority \\ false) do
    if length(state.frames) > 0 do
      # Only flush if we have frames
      frames = state.frames

      # Create batch and broadcast it
      send_batch(frames, is_priority, state.current_pattern_id)

      # Update state
      %{state |
        frames: [],
        batches_sent: state.batches_sent + 1,
        frames_sent: state.frames_sent + length(frames)
      }
    else
      # No frames to flush
      state
    end
  end

  defp send_batch(frames, is_priority, pattern_id) do
    # Log batch details at debug level
    Logger.debug("Sending batch with #{length(frames)} frames, priority=#{is_priority}")

    # Send batch to all controllers via PubSub
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:frames",
      {:frame_batch, frames, is_priority, pattern_id}
    )
  end

  defp schedule_check_flush do
    # Check every 100ms
    Process.send_after(self(), :check_flush, 100)
  end
end
