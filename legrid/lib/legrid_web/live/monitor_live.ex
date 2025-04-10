defmodule LegridWeb.MonitorLive do
  use LegridWeb, :live_view

  alias Legrid.Controller.Interface

  # Import the monitoring component
  import LegridWeb.Components.MonitoringComponent

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket) do
      Phoenix.PubSub.subscribe(Legrid.PubSub, "controller_stats")
      # Activate monitoring when this page is mounted
      try do
        Interface.activate_monitor()
        # Request stats immediately
        request_stats()
      rescue
        _ -> :ok # Silently handle errors if the controller isn't available
      end
    end

    # Safely get controller status
    controller_status = try do
      Interface.status()
    rescue
      _ -> %{connected: false, url: nil}
    end

    socket = socket
    |> assign(:controller_status, controller_status)
    |> assign(:stats, %{
      fps: 0,
      frames_received: 0,
      frames_dropped: 0,
      bandwidth_in: 0,
      bandwidth_out: 0,
      clients: 0,
      last_updated: System.system_time(:second)
    })
    |> assign(:detailed_stats, nil)
    |> assign(:stats_history, [])

    {:ok, socket}
  end

  @impl true
  def terminate(_reason, _socket) do
    # Deactivate monitoring when this page is unmounted
    try do
      Interface.deactivate_monitor()
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
    :ok
  end

  @impl true
  def handle_info({:controller_stats, stats}, socket) do
    # Update basic stats
    new_stats = %{
      fps: stats["fps"] || 0,
      frames_received: stats["frames_received"] || 0,
      frames_dropped: stats["frames_dropped"] || 0,
      bandwidth_in: get_in(stats, ["bandwidth", "in"]) || 0,
      bandwidth_out: get_in(stats, ["bandwidth", "out"]) || 0,
      clients: 0, # Basic stats don't include client count
      last_updated: System.system_time(:second)
    }

    # Add stats to history (keep last 60 entries max)
    history = [new_stats | socket.assigns.stats_history]
    |> Enum.take(60)

    {:noreply, assign(socket, stats: new_stats, stats_history: history)}
  end

  @impl true
  def handle_info({:controller_stats_detailed, stats}, socket) do
    detailed = %{
      system: stats["system"] || %{},
      performance: stats["performance"] || %{},
      client: stats["client"] || %{}
    }

    # Update stats with client count from detailed stats
    new_stats = Map.put(socket.assigns.stats, :clients, get_in(detailed, [:system, "clients"]) || 0)

    {:noreply, assign(socket, detailed_stats: detailed, stats: new_stats)}
  end

  @impl true
  def handle_event("request_stats", _, socket) do
    request_stats()
    {:noreply, socket}
  end

  @impl true
  def handle_event("clear_history", _, socket) do
    {:noreply, assign(socket, stats_history: [])}
  end

  @impl true
  def handle_event("simulate_latency", %{"enabled" => enabled}, socket) do
    # Send config to enable latency simulation
    send_simulation_config(latency: enabled == "true")
    {:noreply, socket}
  end

  @impl true
  def handle_event("simulate_packet_loss", %{"enabled" => enabled}, socket) do
    # Send config to enable packet loss simulation
    send_simulation_config(packet_loss: enabled == "true")
    {:noreply, socket}
  end

  # Helper functions

  defp request_stats do
    # Just update the stats in the LiveView
    # We'll rely on the PubSub subscription to get the actual stats
    try do
      status = Interface.status()
      if status.connected do
        # We need to check if the function is defined first
        case function_exported?(Interface, :request_stats, 0) do
          true -> Interface.request_stats()
          false ->
            # Fallback to direct implementation if needed
            request = %{
              type: "stats_request"
            }
            send_message_to_controller(request)
        end
      end
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
  end

  defp send_simulation_config(options) do
    # Set up simulation config to send to controller
    try do
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

      # Send through Interface if function is available
      status = Interface.status()
      if status.connected do
        case function_exported?(Interface, :send_simulation_config, 1) do
          true -> Interface.send_simulation_config(options)
          false -> send_message_to_controller(config)
        end
      end
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
  end

  # Safe way to send messages to the controller
  defp send_message_to_controller(message) do
    # Use GenServer.call to get the WebSocket connection from Interface
    # This avoids trying to access the socket directly
    try do
      GenServer.call(Legrid.Controller.Interface, {:send_message, message})
    rescue
      _ -> {:error, :not_connected} # Silently handle errors if the controller isn't available
    end
  end
end
