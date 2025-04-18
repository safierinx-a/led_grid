defmodule LegridWeb.ControllerChannel do
  @moduledoc """
  Channel for communicating with hardware controllers.

  This channel handles incoming connections from Raspberry Pi and other
  hardware controllers, sending them frames and receiving status updates.
  """

  use Phoenix.Channel
  require Logger

  @impl true
  def join("controller:lobby", message, socket) do
    # Generate controller ID if not provided
    controller_id = Map.get(message, "controller_id", "controller-#{System.unique_integer([:positive])}")

    Logger.info("Controller joined: #{controller_id}")

    # Subscribe to frames
    Phoenix.PubSub.subscribe(Legrid.PubSub, "controller:frames")

    # Notify controller interface that a new controller has joined
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:events", {:controller_joined, controller_id})

    # Initialize socket assigns
    socket = assign(socket, :controller_id, controller_id)

    # Send initial welcome message
    {:ok, %{status: "connected", controller_id: controller_id}, socket}
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

    # Process flow control if present
    if payload["flow_control"] do
      Legrid.Controller.FrameBuffer.process_flow_control(controller_id, payload["flow_control"])
    end

    # Log at debug level
    Logger.debug("Received display sync from controller #{controller_id}")

    {:noreply, socket}
  end

  @impl true
  def handle_info({:frame, frame}, socket) do
    # Convert frame to binary format for efficient transmission
    frame_binary = frame_to_binary(frame)

    # Base64 encode the binary data for JSON serialization
    encoded_binary = Base.encode64(frame_binary)

    # Push the binary frame to the controller
    push(socket, "frame", %{binary: encoded_binary})

    {:noreply, socket}
  end

  @impl true
  def handle_info({:frame_batch, frames, is_priority, _pattern_id, sequence, timestamp}, socket) do
    # Convert the batch of frames to a single binary message
    batch_binary = frames_batch_to_binary(frames, is_priority, sequence, timestamp)

    # Send the binary batch directly using a raw socket send
    # This bypass Phoenix Channel's JSON encoding for efficiency
    send(self(), {:binary, batch_binary})

    # Log the batch at debug level
    Logger.debug("Sent batch ##{sequence} of #{length(frames)} frames to controller #{socket.assigns.controller_id}")

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

  # Convert frame to binary format for efficient transmission
  defp frame_to_binary(frame) do
    # Convert frame ID to integer
    frame_id = if frame.id do
      frame.id
      |> String.replace(~r/[^0-9a-fA-F]/, "")
      |> String.slice(0, 8)
      |> String.downcase()
      |> case do
        "" -> 0
        hex -> String.to_integer(hex, 16)
      end
    else
      0
    end

    # Serialize pixels to raw list of RGB values
    pixel_data = case frame.pixels do
      pixels when is_list(pixels) ->
        # Convert RGB tuples to binary
        for {r, g, b} <- pixels, byte <- [r, g, b] do
          <<byte::8>>
        end
        |> IO.iodata_to_binary()

      pixels when is_binary(pixels) ->
        # Already binary, just return
        pixels
    end

    # Create binary data in correct format
    <<
      # Header (10 bytes)
      1::8,                           # Protocol version
      1::8,                           # Message type (1 = frame)
      frame_id::little-integer-32,    # Frame ID (4 bytes)
      frame.width::little-integer-16, # Width (2 bytes)
      frame.height::little-integer-16,# Height (2 bytes)

      # Pixel data
      pixel_data::binary
    >>
  end

  # Convert a batch of frames to binary format for batch transmission
  defp frames_batch_to_binary(frames, is_priority, sequence, timestamp) do
    # Frame count and priority flag header
    header = <<
      0xB::8,                            # Batch identifier (1 byte)
      length(frames)::little-integer-32, # Frame count (4 bytes)
      (if is_priority, do: 1, else: 0)::8, # Priority flag (1 byte)
      sequence::little-integer-32,       # Sequence number (4 bytes)
      timestamp::little-integer-64       # Timestamp (8 bytes)
    >>

    # Convert each frame to binary and add to the batch
    frame_binaries = for frame <- frames do
      frame_binary = frame_to_binary(frame)
      # Prefix each frame with its length
      <<byte_size(frame_binary)::little-integer-32, frame_binary::binary>>
    end

    # Combine header and all frame data
    IO.iodata_to_binary([header, frame_binaries])
  end
end
