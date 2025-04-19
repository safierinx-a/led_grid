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

    # Notify controller interface that a controller has joined
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:events", {:controller_joined, controller_id})

    {:ok, socket}
  end

  @impl true
  def join("controller:lobby", payload, socket) do
    # Extract controller_id from payload
    controller_id = Map.get(payload, "controller_id", "unknown-#{:rand.uniform(1000)}")

    Logger.info("Controller #{controller_id} joining lobby channel")

    # Store the controller_id in the socket
    socket = assign(socket, :controller_id, controller_id)

    # Subscribe to controller:socket topic to receive controller-specific batches
    Phoenix.PubSub.subscribe(Legrid.PubSub, "controller:socket")

    # Notify controller interface that a controller has joined
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:events", {:controller_joined, controller_id})

    # Send a message to the controller requesting the first batch
    Process.send_after(self(), {:initiate_polling, controller_id}, 500)

    {:ok, socket}
  end

  @impl true
  def handle_info({:initiate_polling, controller_id}, socket) do
    # Push a message to the controller to request the first batch
    push(socket, "initiate_polling", %{message: "Start polling for frames"})

    Logger.info("Sent initiate_polling message to controller #{controller_id}")

    # Send a diagnostic ping to verify the controller is able to respond
    push(socket, "diagnostic_ping", %{
      timestamp: System.system_time(:millisecond),
      message: "Please respond with diagnostic_pong"
    })

    Logger.info("Sent diagnostic_ping to controller #{controller_id}")

    # Explicitly trigger a batch request to get initial frames
    # This will ensure the controller starts receiving frames even if it doesn't poll immediately
    FrameBuffer.handle_batch_request(controller_id, 0, 60, true)

    # Schedule a follow-up request in case the first one didn't produce frames
    Process.send_after(self(), {:ensure_frames_sent, controller_id}, 1000)

    {:noreply, socket}
  end

  @impl true
  def handle_info({:ensure_frames_sent, controller_id}, socket) do
    # This is a safety mechanism to ensure frames start flowing
    # after controller connection
    if socket.assigns.controller_id == controller_id do
      Logger.debug("Ensuring frames are flowing to controller #{controller_id}")
      FrameBuffer.handle_batch_request(controller_id, 0, 60, true)
    end

    {:noreply, socket}
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
      "frames" => Base.encode64(binary_data),
      "count" => length(frames),
      "priority" => is_priority
    })

    {:noreply, socket}
  end

  @impl true
  def handle_info({:controller_batch, target_controller_id, frames, is_priority, pattern_id, sequence, timestamp}, socket) do
    # Only process if this message is for this controller
    if socket.assigns.controller_id == target_controller_id do
      controller_id = socket.assigns.controller_id
      Logger.info("Sending batch to controller #{controller_id}: #{length(frames)} frames, seq=#{sequence}, pattern=#{inspect(pattern_id)}")

      # Create a proper batch binary format that exactly matches what the controller expects in process_batch_frames:
      # - Byte 0: 0xB (batch identifier)
      # - Bytes 1-4: Frame count (uint32, little-endian)
      # - Byte 5: Priority flag (1 = priority, 0 = normal)
      # - Bytes 6-9: Sequence number (uint32, little-endian)
      # - Bytes 10-17: Timestamp (uint64, little-endian)
      # - For each frame:
      #   - 4 bytes: Frame length (uint32, little-endian)
      #   - N bytes: Frame data

      # Start with the batch header
      frame_count = length(frames)
      priority_flag = if is_priority, do: 1, else: 0
      current_timestamp = timestamp || System.system_time(:millisecond)

      # Batch header
      batch_header = <<0xB::8, frame_count::little-32, priority_flag::8, sequence::little-32, current_timestamp::little-64>>

      # Build frame data
      frames_binary = Enum.reduce(frames, <<>>, fn frame, acc ->
        # Generate the binary data for this frame
        frame_data = encode_frame_binary(frame)
        frame_length = byte_size(frame_data)

        # Combine with the accumulated data
        <<acc::binary, frame_length::little-32, frame_data::binary>>
      end)

      # Combined batch data
      batch_data = <<batch_header::binary, frames_binary::binary>>

      # Log batch details
      Logger.info("Created batch binary: #{byte_size(batch_data)} bytes, #{frame_count} frames, priority=#{priority_flag}, sequence=#{sequence}")

      # Send to controller using the display_batch event
      push(socket, "display_batch", %{
        frames: Base.encode64(batch_data),
        count: frame_count,
        priority: is_priority,
        sequence: sequence
      })

      # Log that the batch was sent
      Logger.info("Batch sent to controller #{controller_id}")
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

    Logger.info("Legacy batch_request from controller #{controller_id}: last_seq=#{last_sequence}, space=#{space_available}, urgent=#{urgent}, payload=#{inspect(payload)}")

    # Forward request to frame buffer
    FrameBuffer.handle_batch_request(controller_id, last_sequence, space_available, urgent)

    # Send a confirmation back to the controller with current server time to help with latency detection
    resp = %{
      status: "request_received",
      timestamp: System.system_time(:millisecond),
      server_sequence: last_sequence
    }

    Logger.debug("Sending request confirmation: #{inspect(resp)}")
    {:reply, {:ok, resp}, socket}
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

    Logger.info("Batch request from controller #{controller_id}: last_seq=#{last_sequence}, space=#{space_available}, urgent=#{urgent}, payload=#{inspect(payload)}")

    # Forward request to frame buffer
    FrameBuffer.handle_batch_request(controller_id, last_sequence, space_available, urgent)

    # Send a confirmation back to the controller with current server time to help with latency detection
    resp = %{
      status: "request_received",
      timestamp: System.system_time(:millisecond),
      server_sequence: last_sequence
    }

    Logger.debug("Sending request confirmation: #{inspect(resp)}")
    {:reply, {:ok, resp}, socket}
  end

  @impl true
  def handle_info({:pattern_changed, pattern_id}, socket) do
    # When a pattern changes, notify the controller directly
    controller_id = socket.assigns.controller_id
    Logger.debug("Notifying controller #{controller_id} of pattern change to #{pattern_id}")

    # Notify the controller of the pattern change
    push(socket, "pattern_changed", %{
      pattern_id: pattern_id,
      timestamp: System.system_time(:millisecond)
    })

    # Also request a batch with urgency to ensure new pattern frames flow immediately
    FrameBuffer.handle_batch_request(controller_id, 0, 60, true)

    {:noreply, socket}
  end

  @impl true
  def handle_in("diagnostic_pong", payload, socket) do
    controller_id = socket.assigns.controller_id
    Logger.info("Received diagnostic_pong from controller #{controller_id}: #{inspect(payload)}")

    # This confirms the controller can receive and process messages
    {:reply, {:ok, %{received: true, server_time: System.system_time(:millisecond)}}, socket}
  end

  @impl true
  def handle_in("batch_ack", payload, socket) do
    controller_id = socket.assigns.controller_id

    # Extract details from payload
    sequence = Map.get(payload, "sequence", 0)
    received_at = Map.get(payload, "received_at", 0)
    rendered = Map.get(payload, "rendered", false)

    Logger.info("Controller #{controller_id} acknowledged batch #{sequence}, rendered: #{rendered}, received at: #{received_at}")

    # Forward acknowledgment to the system
    Phoenix.PubSub.broadcast(
      Legrid.PubSub,
      "controller:events",
      {:batch_acknowledged, controller_id, sequence, rendered, received_at}
    )

    {:reply, {:ok, %{received: true}}, socket}
  end

  # Helper to convert frames to binary format
  defp frames_batch_to_binary(frames, pattern_id, sequence, timestamp) do
    # Convert string pattern_id to an integer hash if it's a string
    pattern_id_int = case pattern_id do
      id when is_integer(id) -> id
      id when is_binary(id) or is_atom(id) ->
        # Convert to string and hash to a 32-bit integer
        id_str = to_string(id)
        :erlang.phash2(id_str, 2_147_483_647) # Max 32-bit signed int
      nil -> 0
      _ -> 0
    end

    # Header: pattern_id (32 bits) + sequence (32 bits) + timestamp (64 bits)
    header = <<pattern_id_int::32, sequence::32, timestamp::64>>

    # Join all frames into a single binary - use a simple and direct format
    # that's easier for controllers to parse
    frames_binary = Enum.reduce(frames, <<>>, fn frame, acc ->
      # Pack pixel data directly as RGB bytes
      pixels_data = for {r, g, b} <- frame.pixels, into: <<>> do
        <<r::8, g::8, b::8>>
      end

      # Each frame: length (16 bits) + RGB data
      pixel_count = length(frame.pixels)
      <<acc::binary, pixel_count::16, pixels_data::binary>>
    end)

    # Return header + frames data
    <<header::binary, frames_binary::binary>>
  end

  # Helper to encode a single frame in binary format
  defp encode_frame_binary(frame) do
    # Version 1, message type 1 (full frame)
    version = 1
    msg_type = 1
    frame_id = System.system_time(:millisecond) |> rem(0xFFFFFFFF)
    width = Map.get(frame, :width, 25)
    height = Map.get(frame, :height, 24)

    # Header
    header = <<version::8, msg_type::8, frame_id::little-32, width::little-16, height::little-16>>

    # Pixel data as RGB bytes
    pixel_data = for {r, g, b} <- frame.pixels, into: <<>> do
      <<r::8, g::8, b::8>>
    end

    # Full frame
    <<header::binary, pixel_data::binary>>
  end
end
