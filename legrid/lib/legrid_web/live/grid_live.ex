defmodule LegridWeb.GridLive do
  use LegridWeb, :live_view

  alias Legrid.Patterns.{Registry, Runner}
  alias Legrid.Controller.Interface
  alias Legrid.Frame

  import LegridWeb.Components.MonitoringComponent

  @grid_width 25
  @grid_height 24
  @pixel_size 20 # Size of each LED in the web interface

  @impl true
  def mount(_params, _session, socket) do
    # Subscribe to frame updates
    if connected?(socket) do
      Runner.subscribe()
      Phoenix.PubSub.subscribe(Legrid.PubSub, "controller_stats")
      # We don't activate monitoring here since this is just the grid view
      # which doesn't need detailed stats
    end

    # Get available patterns
    patterns = Registry.list_patterns()

    socket = socket
    |> assign(:patterns, patterns)
    |> assign(:current_pattern, nil)
    |> assign(:pattern_metadata, nil)
    |> assign(:pixels, blank_pixels())
    |> assign(:controller_status, Interface.status())
    |> assign(:pattern_params, %{})
    |> assign(:grid_width, @grid_width)
    |> assign(:grid_height, @grid_height)
    |> assign(:pixel_size, @pixel_size)
    |> assign(:stats, %{
      fps: 0,
      frames_received: 0,
      frames_dropped: 0,
      bandwidth_in: 0,
      bandwidth_out: 0,
      clients: 0,
      last_updated: nil
    })
    |> assign(:detailed_stats, nil)
    |> assign(:stats_history, [])
    |> assign(:monitoring_active, false)

    {:ok, socket}
  end

  @impl true
  def handle_event("select-pattern", %{"pattern_id" => pattern_id}, socket) do
    case Registry.get_pattern(pattern_id) do
      {:ok, metadata} ->
        # Extract default params
        default_params = metadata.parameters
        |> Enum.map(fn {key, param} -> {key, param.default} end)
        |> Enum.into(%{})

        {:noreply, assign(socket,
          pattern_params: default_params,
          current_pattern: pattern_id,
          pattern_metadata: metadata
        )}

      {:error, _} ->
        {:noreply, socket}
    end
  end

  @impl true
  def handle_event("start-pattern", %{"params" => params}, socket) do
    pattern_id = socket.assigns.current_pattern

    if pattern_id do
      Runner.start_pattern(pattern_id, params)
      {:noreply, socket}
    else
      {:noreply, socket}
    end
  end

  @impl true
  def handle_event("stop-pattern", _params, socket) do
    Runner.stop_pattern()
    {:noreply, socket}
  end

  @impl true
  def handle_event("update-param", %{"key" => key, "value" => value}, socket) do
    # Convert value to appropriate type
    params = socket.assigns.pattern_params

    pattern_id = socket.assigns.current_pattern
    {:ok, metadata} = Registry.get_pattern(pattern_id)

    param_def = metadata.parameters[key]
    converted_value = convert_param_value(value, param_def.type)

    updated_params = Map.put(params, key, converted_value)

    {:noreply, assign(socket, pattern_params: updated_params)}
  end

  @impl true
  def handle_event("update-param", %{"_target" => [_form, param_name], "params" => params}, socket) do
    # Extract the parameter value from the form params
    value = params[param_name]
    pattern_params = socket.assigns.pattern_params

    pattern_id = socket.assigns.current_pattern
    {:ok, metadata} = Registry.get_pattern(pattern_id)

    param_def = metadata.parameters[param_name]
    converted_value = convert_param_value(value, param_def.type)

    # Update the parameter value
    updated_params = Map.put(pattern_params, param_name, converted_value)

    {:noreply, assign(socket, pattern_params: updated_params)}
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

  @impl true
  def handle_event("toggle_monitoring", _params, socket) do
    # Toggle the monitoring panel
    monitoring_active = !socket.assigns.monitoring_active

    # Activate or deactivate detailed monitoring based on panel visibility
    if monitoring_active do
      Interface.activate_monitor()
      request_stats() # Request stats immediately when panel is shown
    else
      Interface.deactivate_monitor()
    end

    {:noreply, assign(socket, monitoring_active: monitoring_active)}
  end

  @impl true
  def handle_info({:frame, frame}, socket) do
    {:noreply, assign(socket, pixels: frame.pixels)}
  end

  @impl true
  def handle_info({:controller_stats, stats}, socket) do
    # Update basic stats - don't log every update
    new_stats = %{
      fps: stats["fps"] || 0,
      frames_received: stats["frames_received"] || 0,
      frames_dropped: stats["frames_dropped"] || 0,
      bandwidth_in: get_in(stats, ["bandwidth", "in"]) || 0,
      bandwidth_out: get_in(stats, ["bandwidth", "out"]) || 0,
      clients: socket.assigns.stats.clients, # Preserve client count
      last_updated: DateTime.utc_now()
    }

    # Add stats to history (keep last 60 entries max)
    history = [new_stats | socket.assigns.stats_history]
    |> Enum.take(60)

    {:noreply, assign(socket, stats: new_stats, stats_history: history)}
  end

  @impl true
  def handle_info({:controller_stats_detailed, stats}, socket) do
    # Only log if there's a significant change in system or performance metrics
    detailed = %{
      system: stats["system"] || %{},
      performance: stats["performance"] || %{},
      client: stats["client"] || %{}
    }

    # Update stats with client count from detailed stats
    new_stats = Map.put(socket.assigns.stats, :clients, get_in(detailed, [:system, "clients"]) || 0)

    {:noreply, assign(socket, detailed_stats: detailed, stats: new_stats)}
  end

  # Helper functions

  defp blank_pixels do
    for _y <- 0..(@grid_height - 1), _x <- 0..(@grid_width - 1), do: {0, 0, 0}
  end

  defp convert_param_value(value, :integer), do: String.to_integer(value)
  defp convert_param_value(value, :float), do: String.to_float(value)
  defp convert_param_value("true", :boolean), do: true
  defp convert_param_value("false", :boolean), do: false
  defp convert_param_value(value, :string), do: value
  defp convert_param_value(value, _), do: value

  defp rgb_to_css({r, g, b}), do: "rgb(#{r}, #{g}, #{b})"

  # Format bytes to human-readable string
  defp format_memory(bytes) when is_integer(bytes) do
    cond do
      bytes >= 1_000_000_000 -> "#{Float.round(bytes / 1_000_000_000, 2)} GB"
      bytes >= 1_000_000 -> "#{Float.round(bytes / 1_000_000, 2)} MB"
      bytes >= 1_000 -> "#{Float.round(bytes / 1_000, 2)} KB"
      true -> "#{bytes} B"
    end
  end
  defp format_memory(_), do: "0 B"

  # Format bandwidth bytes per second
  defp format_bandwidth(bytes_per_sec) when is_integer(bytes_per_sec) do
    "#{format_memory(bytes_per_sec)}/s"
  end
  defp format_bandwidth(_), do: "0 B/s"

  # Format percentage value with % sign
  defp format_percent(value) when is_number(value) do
    "#{Float.round(value, 1)}%"
  end
  defp format_percent(_), do: "0%"

  defp request_stats do
    # Just update the stats in the LiveView
    # We'll rely on the PubSub subscription to get the actual stats
    status = Interface.status()
    if status.connected do
      # We need to check if the function is defined first
      case function_exported?(Interface, :request_stats, 0) do
        true -> Interface.request_stats()
        false ->
          # Fallback to old implementation (if any changes were not applied)
          :ok
      end
    end
  end

  defp send_simulation_config(options) do
    # Let the Interface module handle the config sending
    status = Interface.status()
    if status.connected do
      # We need to check if the function is defined first
      case function_exported?(Interface, :send_simulation_config, 1) do
        true -> Interface.send_simulation_config(options)
        false ->
          # Fallback to old implementation (if any changes were not applied)
          :ok
      end
    end
  end
end
