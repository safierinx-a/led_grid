defmodule Legrid.Controller.Interface do
  @moduledoc """
  Interface for communicating with LED grid controllers.

  This module handles sending frames to the physical LED grid controller
  via websockets. It manages connection state and reconnection attempts.
  """

  use GenServer

  alias Legrid.Frame

  # Client API

  @doc """
  Starts the controller interface.

  Options:
  - url: Websocket URL of the controller
  - width: Width of the LED grid
  - height: Height of the LED grid
  - reconnect_timeout: Time in ms to wait before reconnecting
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Send a frame to the controller.
  """
  def send_frame(%Frame{} = frame) do
    GenServer.cast(__MODULE__, {:send_frame, frame})
  end

  @doc """
  Get the current status of the controller connection.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  @doc """
  Request statistics from the controller.
  """
  def request_stats do
    GenServer.cast(__MODULE__, :request_stats)
  end

  @doc """
  Send simulation configuration to the controller.
  """
  def send_simulation_config(options) do
    GenServer.cast(__MODULE__, {:send_simulation_config, options})
  end

  # Server callbacks

  @impl true
  def init(opts) do
    url = Keyword.get(opts, :url, "ws://localhost:8080")
    width = Keyword.get(opts, :width, 25)
    height = Keyword.get(opts, :height, 24)
    reconnect_timeout = Keyword.get(opts, :reconnect_timeout, 5000)

    state = %{
      url: url,
      width: width,
      height: height,
      reconnect_timeout: reconnect_timeout,
      socket: nil,
      connected: false,
      reconnect_timer: nil,
      last_frame: nil,
      stats_timer: nil,
      last_stats_update: nil,
      last_detailed_stats: nil,
      monitor_active: false  # Track if /monitor page is active
    }

    # Subscribe to frames
    Legrid.Patterns.Runner.subscribe()

    # Don't start a timer immediately, controller will send periodic updates
    # We'll only request stats when the monitor page is active
    stats_timer = nil

    # Attempt to connect immediately
    {:ok, %{state | stats_timer: stats_timer} |> connect()}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      connected: state.connected,
      url: state.url,
      width: state.width,
      height: state.height
    }

    {:reply, status, state}
  end

  @impl true
  def handle_call({:send_message, message}, _from, state) do
    if state.connected do
      # Encode and send the message
      message_data = Jason.encode!(message)
      IO.puts("Sending message to controller: #{inspect(message)}")

      case WebSockex.send_frame(state.socket, {:text, message_data}) do
        :ok ->
          IO.puts("Message sent successfully")
          {:reply, :ok, state}
        {:error, reason} ->
          IO.puts("Error sending message: #{inspect(reason)}")
          {:reply, {:error, reason}, state}
      end
    else
      {:reply, {:error, :not_connected}, state}
    end
  end

  @impl true
  def handle_call({:set_monitor_active, active}, _from, state) do
    # When monitor page becomes active, immediately request detailed stats
    if active && !state.monitor_active do
      Process.send_after(self(), :request_detailed_stats, 100)
    end

    # If monitor is deactivated, cancel any pending stats timers
    if !active && state.monitor_active && state.stats_timer do
      Process.cancel_timer(state.stats_timer)
    end

    {:reply, :ok, %{state | monitor_active: active}}
  end

  @impl true
  def handle_cast({:send_frame, frame}, state) do
    if state.connected do
      # Convert frame to binary format instead of JSON
      frame_binary = frame_to_binary(frame)

      # Send the binary frame data
      WebSockex.send_frame(state.socket, {:binary, frame_binary})

      {:noreply, %{state | last_frame: frame}}
    else
      # Not connected, just update last frame
      {:noreply, %{state | last_frame: frame}}
    end
  end

  @impl true
  def handle_cast(:request_stats, state) do
    if state.connected do
      request = %{
        type: "stats_request"
      }

      # Send the stats request
      IO.puts("Sending stats request to controller")
      case WebSockex.send_frame(state.socket, {:text, Jason.encode!(request)}) do
        :ok -> IO.puts("Stats request sent successfully")
        {:error, reason} -> IO.puts("Error sending stats request: #{inspect(reason)}")
      end
    end

    {:noreply, state}
  end

  @impl true
  def handle_cast({:send_simulation_config, options}, state) do
    if state.connected do
      # Set up simulation config to send to controller
      config = %{
        type: "simulation_config"
      }

      config = if Keyword.has_key?(options, :latency) do
        Map.put(config, :simulate_latency, Keyword.get(options, :latency))
      else
        config
      end

      config = if Keyword.has_key?(options, :packet_loss) do
        Map.put(config, :simulate_packet_loss, Keyword.get(options, :packet_loss))
      else
        config
      end

      # Send the simulation config
      WebSockex.send_frame(state.socket, {:text, Jason.encode!(config)})
    end

    {:noreply, state}
  end

  @impl true
  def handle_info({:frame, frame}, state) do
    # When we receive a frame from the pattern runner, send it to the controller
    if state.connected do
      # Convert frame to binary format
      frame_binary = frame_to_binary(frame)

      # Send the binary frame data
      WebSockex.send_frame(state.socket, {:binary, frame_binary})

      {:noreply, %{state | last_frame: frame}}
    else
      # Not connected, just update last frame
      {:noreply, %{state | last_frame: frame}}
    end
  end

  @impl true
  def handle_info(:connect, state) do
    {:noreply, connect(state)}
  end

  @impl true
  def handle_info({:websocket, :disconnected}, state) do
    # Socket disconnected, clean up and schedule reconnect
    if state.reconnect_timer, do: Process.cancel_timer(state.reconnect_timer)
    reconnect_timer = Process.send_after(self(), :connect, state.reconnect_timeout)

    {:noreply, %{state | connected: false, socket: nil, reconnect_timer: reconnect_timer}}
  end

  @impl true
  def handle_info({:websocket, :connected}, state) do
    # Just acknowledge the connection is established
    IO.puts("Interface acknowledges connection established")

    # Request stats immediately on successful connection
    Process.send_after(self(), :request_initial_stats, 1000)

    {:noreply, state}
  end

  @impl true
  def handle_info(:request_initial_stats, state) do
    IO.puts("Requesting initial stats after connection")
    if state.connected do
      request = %{
        type: "stats_request"
      }

      # Send the stats request
      case WebSockex.send_frame(state.socket, {:text, Jason.encode!(request)}) do
        :ok -> IO.puts("Initial stats request sent successfully")
        {:error, reason} -> IO.puts("Error sending initial stats request: #{inspect(reason)}")
      end
    end

    {:noreply, state}
  end

  @impl true
  def handle_info({:websocket, {:message, %{"type" => "status"} = data}}, state) do
    # Handle status message
    IO.puts("Received status message from controller: #{inspect(data)}")
    {:noreply, state}
  end

  @impl true
  def handle_info({:websocket, {:message, %{"type" => "stats_update"} = data}}, state) do
    # Store the last stats update to avoid sending duplicate stats
    # Forward stats updates to subscribers
    IO.puts("Received stats_update from controller")
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller_stats", {:controller_stats, data})
    {:noreply, %{state | last_stats_update: data}}
  end

  @impl true
  def handle_info({:websocket, {:message, %{"type" => "stats_response"} = data}}, state) do
    # Store the last detailed stats to avoid duplicate requests
    # Forward detailed stats to subscribers
    IO.puts("Received stats_response from controller")
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller_stats", {:controller_stats_detailed, data})
    {:noreply, %{state | last_detailed_stats: data}}
  end

  @impl true
  def handle_info({:websocket, {:message, msg}}, state) do
    # Handle other messages
    IO.puts("Received other message from controller: #{inspect(msg)}")
    {:noreply, state}
  end

  @impl true
  def handle_info(:periodic_stats_request, state) do
    # Only request stats periodically if the monitor page is active
    # Otherwise rely on controller's automatic updates
    stats_timer = if state.monitor_active && state.connected do
      # Send a detailed stats request
      request = %{
        type: "stats_request"
      }

      # Send the stats request
      WebSockex.send_frame(state.socket, {:text, Jason.encode!(request)})

      # Schedule the next request
      Process.send_after(self(), :periodic_stats_request, 5000)
    else
      nil
    end

    {:noreply, %{state | stats_timer: stats_timer}}
  end

  @impl true
  def handle_info(:request_detailed_stats, state) do
    # Request detailed stats immediately
    if state.connected do
      request = %{
        type: "stats_request"
      }

      # Send the stats request
      WebSockex.send_frame(state.socket, {:text, Jason.encode!(request)})

      # If monitor is active, schedule periodic updates
      stats_timer = if state.monitor_active do
        Process.send_after(self(), :periodic_stats_request, 5000)
      else
        nil
      end

      {:noreply, %{state | stats_timer: stats_timer}}
    else
      {:noreply, state}
    end
  end

  # Helper functions

  defp connect(state) do
    # Cancel any existing reconnect timer
    if state.reconnect_timer, do: Process.cancel_timer(state.reconnect_timer)

    # Attempt to connect to the controller
    IO.puts("Attempting to connect to controller at #{state.url}")
    case WebSockex.start_link(state.url, __MODULE__.WebSocketClient, %{parent: self()}) do
      {:ok, socket} ->
        IO.puts("Successfully connected to controller at #{state.url}")
        # Send initial configuration
        config = %{
          type: "config",
          width: state.width,
          height: state.height
        }

        # Send initial config - no need to log the actual config data
        IO.puts("Sending initial config to controller")
        case WebSockex.send_frame(socket, {:text, Jason.encode!(config)}) do
          :ok -> :ok
          {:error, reason} -> IO.puts("Error sending initial config: #{inspect(reason)}")
        end

        # Resend the last frame if we have one
        if state.last_frame do
          frame_binary = frame_to_binary(state.last_frame)
          WebSockex.send_frame(socket, {:binary, frame_binary})
        end

        # Ensure stats timer is running
        stats_timer = if state.stats_timer do
          state.stats_timer
        else
          Process.send_after(self(), :periodic_stats_request, 5000)
        end

        %{state | socket: socket, connected: true, reconnect_timer: nil, stats_timer: stats_timer}

      {:error, reason} ->
        # Failed to connect, schedule reconnect
        IO.puts("Failed to connect to controller: #{inspect(reason)}")
        reconnect_timer = Process.send_after(self(), :connect, state.reconnect_timeout)
        %{state | connected: false, socket: nil, reconnect_timer: reconnect_timer}
    end
  end

  # WebSocket client module
  defmodule WebSocketClient do
    @moduledoc false
    use WebSockex

    @impl true
    def handle_connect(conn, state) do
      # Only log the fact of connection, not the details
      IO.puts("WebSocketClient connected")
      send(state.parent, {:websocket, :connected})
      {:ok, state}
    end

    @impl true
    def handle_frame({type, msg}, state) do
      # Don't log every frame received - too noisy
      try do
        # Parse JSON message
        parsed_msg = Jason.decode!(msg)

        # Only log important messages, not frame_ack which happens 30+ times per second
        if parsed_msg["type"] != "frame_ack" do
          IO.puts("WebSocketClient received message type: #{parsed_msg["type"]}")
        end

        # Forward message to parent process based on type
        cond do
          parsed_msg["type"] == "stats_update" ->
            send(state.parent, {:websocket, {:message, parsed_msg}})

          parsed_msg["type"] == "stats_response" ->
            send(state.parent, {:websocket, {:message, parsed_msg}})

          parsed_msg["type"] == "status" ->
            send(state.parent, {:websocket, {:message, parsed_msg}})

          parsed_msg["type"] == "config_ack" ->
            send(state.parent, {:websocket, {:message, parsed_msg}})

          parsed_msg["type"] == "frame_ack" ->
            # Forward but don't log frame_ack messages - they're too numerous
            send(state.parent, {:websocket, {:message, parsed_msg}})

          true ->
            # Don't print "Received other message" for every unknown message type
            # Only log truly unexpected message types
            IO.puts("Received unexpected message type: #{parsed_msg["type"]}")
            send(state.parent, {:websocket, {:message, parsed_msg}})
        end
      rescue
        e ->
          # Log error but don't crash on parse errors
          IO.puts("Error parsing WebSocket message: #{inspect e}")
      end

      {:ok, state}
    end

    @impl true
    def handle_disconnect(disconnect_map, state) do
      IO.puts("WebSocketClient disconnected: #{inspect(disconnect_map)}")
      send(state.parent, {:websocket, :disconnected})
      {:reconnect, state}
    end
  end

  # Add functions to handle monitor page activation/deactivation
  def activate_monitor do
    GenServer.call(__MODULE__, {:set_monitor_active, true})
  end

  def deactivate_monitor do
    GenServer.call(__MODULE__, {:set_monitor_active, false})
  end

  # Helper function to convert frame to binary format compatible with mock-controller
  defp frame_to_binary(frame) do
    # Mock-controller binary format:
    # - 1 byte: protocol version (1)
    # - 1 byte: message type (1 = frame, 2 = delta frame)
    # - 4 bytes: frame ID (uint32)
    # - 2 bytes: width (uint16)
    # - 2 bytes: height (uint16)
    # - Remaining bytes: RGB pixel data (1 byte per channel)

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
end
