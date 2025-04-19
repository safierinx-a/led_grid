defmodule LegridWeb.ControllerChannel do
  @moduledoc """
  Channel for communicating with hardware controllers.

  This channel handles incoming connections from Raspberry Pi and other
  hardware controllers, sending them frames and receiving status updates.
  """

  use Phoenix.Channel
  require Logger
  alias Legrid.Controller.FrameBuffer

  @impl true
  def join("controller:" <> controller_id, payload, socket) do
    Logger.info("Controller #{controller_id} joining channel")

    # Store the controller_id in the socket
    socket = assign(socket, :controller_id, controller_id)

    # Subscribe to controller:socket topic to receive controller-specific batches
    Phoenix.PubSub.subscribe(Legrid.PubSub, "controller:socket")

    {:ok, socket}
  end

  @impl true
  def terminate(reason, socket) do
    controller_id = socket.assigns.controller_id
    Logger.info("Controller disconnected: #{controller_id}, reason: #{inspect(reason)}")

    # Notify controller interface that a controller has left
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:events", {:controller_left, controller_id})

    :ok
  end

  @impl true
  def handle_in("ping", _payload, socket) do
    {:reply, {:ok, %{status: "pong"}}, socket}
  end

  @impl true
  def handle_in("stats", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Forward stats to interface
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:events", {:stats_update, controller_id, payload})

    # Log stats at debug level to avoid noise
    Logger.debug("Received stats from controller #{controller_id}: #{inspect(payload)}")

    {:noreply, socket}
  end

  @impl true
  def handle_in("display_sync", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Forward display sync information to interface
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:events",
      {:display_sync, controller_id, payload}
    )

    # Log at debug level
    Logger.debug("Received display sync from controller #{controller_id}: buffer status: #{inspect(payload["buffer_stats"])}")

    {:noreply, socket}
  end

  @impl true
  def handle_in("batch_ready", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Extract sequence number and buffer state
    processed_sequence = Map.get(payload, "processed_sequence", 0)
    buffer_fullness = Map.get(payload, "buffer_fullness", 0.0)
    buffer_capacity = Map.get(payload, "buffer_capacity", 0)

    # Forward batch ready signal to the frame buffer manager
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:events",
      {:batch_ready, controller_id, processed_sequence, buffer_fullness, buffer_capacity}
    )

    # Log at debug level
    Logger.debug("Controller #{controller_id} ready for next batch after #{processed_sequence}, buffer fullness: #{buffer_fullness}")

    {:noreply, socket}
  end

  @impl true
  def handle_info({:frame, frame_data}, socket) do
    push(socket, "display", %{
      "frame" => frame_data
    })
    {:noreply, socket}
  end

  @impl true
  def handle_info({:frame_batch, frames, is_priority, pattern_id, sequence, timestamp}, socket) do
    # This is the broadcast-to-all method which is being phased out in favor of controller-specific batches
    # But we'll keep it for backward compatibility during the transition
    binary_data = frames_batch_to_binary(frames, pattern_id, sequence, timestamp)

    push(socket, "display_batch", %{
      "frames" => binary_data,
      "count" => length(frames),
      "priority" => is_priority
    })

    {:noreply, socket}
  end

  @impl true
  def handle_info({:controller_batch, target_controller_id, frames, is_priority, pattern_id, sequence, timestamp}, socket) do
    # Only process if this message is for this controller
    if socket.assigns.controller_id == target_controller_id do
      Logger.debug("Sending batch to controller #{target_controller_id}: #{length(frames)} frames, seq=#{sequence}")

      # Convert frames to binary format
      batch_data = frames_batch_to_binary(frames, pattern_id, sequence, timestamp)

      # Push the binary data to the socket
      push(socket, "frames_batch", %{
        data: batch_data,
        sequence: sequence,
        count: length(frames),
        pattern_id: pattern_id,
        timestamp: timestamp,
        is_priority: is_priority
      })
    end

    {:noreply, socket}
  end

  @impl true
  def handle_info({:binary, binary_data}, socket) do
    # Send the binary data directly on the raw websocket
    # This avoids any Phoenix Channel overhead, Base64 encoding, etc.
    socket.transport_pid |> send({:socket_push, :binary, binary_data})

    {:noreply, socket}
  end

  @impl true
  def handle_info({:request_stats, _}, socket) do
    # Forward request to the controller
    push(socket, "request_stats", %{})

    {:noreply, socket}
  end

  @impl true
  def handle_info({:request_detailed_stats, _}, socket) do
    # Forward request to the controller
    push(socket, "request_detailed_stats", %{})

    {:noreply, socket}
  end

  @impl true
  def handle_info({:simulation_config, options}, socket) do
    # Forward simulation config to the controller
    push(socket, "simulation_config", options)

    {:noreply, socket}
  end

  @impl true
  def handle_in("batch_request", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Extract request details
    last_sequence = Map.get(payload, "last_sequence", 0)
    space_available = Map.get(payload, "space_available", 60)
    urgent = Map.get(payload, "urgent", false)

    Logger.debug("Batch request from controller #{controller_id}: last_seq=#{last_sequence}, space=#{space_available}, urgent=#{urgent}")

    # Forward request to frame buffer
    FrameBuffer.handle_batch_request(controller_id, last_sequence, space_available, urgent)

    {:reply, {:ok, %{status: "request_received"}}, socket}
  end

  @impl true
  def handle_info({:frame, frame, pattern_id}, socket) do
    # Legacy single frame support - push directly to socket
    push(socket, "frame", %{
      data: frame,
      pattern_id: pattern_id,
      timestamp: System.system_time(:millisecond)
    })

    {:noreply, socket}
  end

  @impl true
  def handle_in("request_batch", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Extract request details
    last_sequence = Map.get(payload, "last_sequence", 0)
    space_available = Map.get(payload, "space_available", 60)
    urgent = Map.get(payload, "urgent", false)

    Logger.debug("Batch request from controller #{controller_id}: last_seq=#{last_sequence}, space=#{space_available}, urgent=#{urgent}")

    # Forward request to frame buffer
    FrameBuffer.handle_batch_request(controller_id, last_sequence, space_available, urgent)

    {:reply, {:ok, %{status: "request_received"}}, socket}
  end

  # Helper to convert frames to binary format
  defp frames_batch_to_binary(frames, pattern_id, sequence, timestamp) do
    # Header: pattern_id (32 bits) + sequence (32 bits) + timestamp (64 bits)
    header = <<pattern_id::32, sequence::32, timestamp::64>>

    # Join all frames into a single binary
    frames_binary = Enum.reduce(frames, <<>>, fn frame, acc ->
      # Each frame: length (16 bits) + data
      frame_size = byte_size(frame)
      <<acc::binary, frame_size::16, frame::binary>>
    end)

    # Return header + frames data
    <<header::binary, frames_binary::binary>>
  end
end
