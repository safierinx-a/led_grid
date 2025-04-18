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
  - Implements flow control based on controller feedback
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

  @doc """
  Process controller flow control feedback.
  """
  def process_flow_control(controller_id, flow_control) do
    GenServer.cast(__MODULE__, {:flow_control, controller_id, flow_control})
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
      frames_sent: 0,
      batch_sequence: 1,  # Sequence counter for batches
      last_batch_time: System.monotonic_time(:millisecond),  # Track batch timing
      # Flow control state for each controller
      controllers: %{},
      # Flow control defaults
      send_rate_limit: 2,  # Max batches per second per controller
      batch_size_limit: batch_size  # Current dynamic batch size
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

    # Check if we're over the dynamic batch size limit
    current_batch_size = min(state.batch_size, state.batch_size_limit)

    # Flush if we've reached the batch size
    if length(new_state.frames) >= current_batch_size do
      # Flush all frames
      {:noreply, do_flush(new_state, is_priority || pattern_changed)}
    else
      # Continue collecting frames
      {:noreply, new_state}
    end
  end

  @impl true
  def handle_cast({:flow_control, controller_id, flow_control}, state) do
    Logger.debug("Received flow control from controller #{controller_id}: buffer fullness=#{flow_control["buffer_fullness"]}, can_receive=#{flow_control["can_receive"]}")

    # Update controller state with flow control info
    controllers = Map.update(
      state.controllers,
      controller_id,
      %{
        last_update: System.monotonic_time(:millisecond),
        buffer_fullness: flow_control["buffer_fullness"],
        can_receive: flow_control["can_receive"],
        sequence_received: flow_control["sequence_received"],
        fps: flow_control["actual_fps"]
      },
      fn controller ->
        %{controller |
          last_update: System.monotonic_time(:millisecond),
          buffer_fullness: flow_control["buffer_fullness"],
          can_receive: flow_control["can_receive"],
          sequence_received: flow_control["sequence_received"],
          fps: flow_control["actual_fps"]
        }
      end
    )

    # Adjust batch size based on controller feedback
    # For now, we'll use the most conservative approach: if any controller
    # is too full, we'll reduce batch size for everyone
    new_batch_size_limit = calculate_dynamic_batch_size(controllers)

    # Update state
    new_state = %{state |
      controllers: controllers,
      batch_size_limit: new_batch_size_limit
    }

    # If any controller is empty but we have frames, flush immediately
    # This helps maintain continuous playback
    if has_empty_controllers?(controllers) && length(state.frames) >= state.min_frames do
      Logger.debug("Controller buffer low, flushing immediately to maintain playback")
      {:noreply, do_flush(new_state)}
    else
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
    # Calculate average controller buffer fullness
    avg_fullness = case Map.values(state.controllers) do
      [] -> 0.0
      controllers ->
        controllers
        |> Enum.map(fn c -> c.buffer_fullness end)
        |> Enum.sum()
        |> Kernel./(length(controllers))
    end

    status = %{
      frames_in_buffer: length(state.frames),
      batch_size: state.batch_size,
      dynamic_batch_size: state.batch_size_limit,
      batches_sent: state.batches_sent,
      frames_sent: state.frames_sent,
      current_pattern_id: state.current_pattern_id,
      controller_count: map_size(state.controllers),
      avg_controller_fullness: avg_fullness
    }

    {:reply, status, state}
  end

  @impl true
  def handle_info(:check_flush, state) do
    # Check if we should flush based on time
    now = System.monotonic_time(:millisecond)
    time_since_last_frame = now - state.last_frame_time
    time_since_last_batch = now - state.last_batch_time

    # Flush if:
    # 1. Enough time has passed since last new frame AND we have minimum frames
    # 2. OR if enough time has passed since last batch AND we have any frames (to maintain playback)
    state = cond do
      time_since_last_frame >= state.max_delay && length(state.frames) >= state.min_frames ->
        Logger.debug("Flushing batch due to max delay since last frame")
        do_flush(state)

      time_since_last_batch >= 1000 && length(state.frames) > 0 ->
        Logger.debug("Flushing batch to maintain playback rhythm")
        do_flush(state)

      true ->
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
      current_sequence = state.batch_sequence

      # Create batch and broadcast it
      send_batch(frames, is_priority, state.current_pattern_id, current_sequence)

      # Update state
      %{state |
        frames: [],
        batches_sent: state.batches_sent + 1,
        frames_sent: state.frames_sent + length(frames),
        batch_sequence: current_sequence + 1,
        last_batch_time: System.monotonic_time(:millisecond)
      }
    else
      # No frames to flush
      state
    end
  end

  defp send_batch(frames, is_priority, pattern_id, sequence) do
    # Get current timestamp for this batch
    timestamp = System.system_time(:millisecond)

    # Log batch details at debug level
    Logger.debug("Sending batch ##{sequence} with #{length(frames)} frames, priority=#{is_priority}")

    # Send batch to all controllers via PubSub
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:frames",
      {:frame_batch, frames, is_priority, pattern_id, sequence, timestamp}
    )
  end

  defp schedule_check_flush do
    # Check every 100ms
    Process.send_after(self(), :check_flush, 100)
  end

  # Check if any controllers have nearly empty buffers
  defp has_empty_controllers?(controllers) do
    Enum.any?(controllers, fn {_id, controller} ->
      controller.buffer_fullness < 0.2 && controller.can_receive
    end)
  end

  # Calculate dynamic batch size based on controller feedback
  defp calculate_dynamic_batch_size(controllers) do
    case Map.values(controllers) do
      [] ->
        # No controllers, use default
        120

      controller_list ->
        # Find the minimum appropriate batch size based on buffer fullness
        controller_list
        |> Enum.map(fn controller ->
          cond do
            # Controller buffer nearly full - small batches
            controller.buffer_fullness > 0.8 -> 30
            # Controller buffer moderately full
            controller.buffer_fullness > 0.6 -> 60
            # Controller buffer has space
            controller.buffer_fullness > 0.4 -> 90
            # Controller buffer has plenty of space
            true -> 120
          end
        end)
        |> Enum.min()
    end
  end
end
