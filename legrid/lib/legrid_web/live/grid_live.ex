defmodule LegridWeb.GridLive do
  use LegridWeb, :live_view

  alias Legrid.Patterns.{Registry, Runner}
  alias Legrid.Controller.Interface

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

    # Safely get controller status
    controller_status = try do
      Interface.status()
    rescue
      _ -> %{connected: false, url: nil, width: @grid_width, height: @grid_height}
    end

    socket = socket
    |> assign(:patterns, patterns)
    |> assign(:current_pattern, nil)
    |> assign(:pattern_metadata, nil)
    |> assign(:pixels, blank_pixels())
    |> assign(:controller_status, controller_status)
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
      last_updated: System.system_time(:second)
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

        # Preserve shared parameters from previous pattern if they exist
        preserved_params = if socket.assigns.current_pattern do
          # List of global parameters to preserve
          global_params = ["brightness", "color_scheme", "speed"]

          # Keep values of global parameters from current pattern
          socket.assigns.pattern_params
          |> Map.take(global_params)
          |> Enum.filter(fn {key, _value} ->
            # Only preserve if the new pattern also has this parameter
            Map.has_key?(metadata.parameters, key)
          end)
          |> Enum.into(%{})
        else
          %{}
        end

        # Merge the preserved params with default params (preserved takes precedence)
        merged_params = Map.merge(default_params, preserved_params)

        {:noreply, assign(socket,
          pattern_params: merged_params,
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
    try do
      if monitoring_active do
        Interface.activate_monitor()
        request_stats() # Request stats immediately when panel is shown
      else
        Interface.deactivate_monitor()
      end
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
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
      last_updated: System.system_time(:second)
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
            # Fallback to old implementation (if any changes were not applied)
            :ok
        end
      end
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
  end

  defp send_simulation_config(options) do
    # Let the Interface module handle the config sending
    try do
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
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
  end

    # Filter parameters based on visible_parameters metadata and current variant
  defp filter_visible_parameters(metadata, pattern_params) do
    case Map.get(metadata, :visible_parameters) do
      nil ->
        # If no visible_parameters specified, show all parameters
        metadata.parameters

      visible_params ->
        # Determine current variant based on pattern_params
        variant = determine_current_variant(metadata, pattern_params)

        # Get the list of visible parameters for this variant
        visible_param_names = Map.get(visible_params, variant, [])

        # Filter parameters to only show the visible ones
        metadata.parameters
        |> Enum.filter(fn {key, _param} -> key in visible_param_names end)
        |> Enum.into(%{})
    end
  end

  # Determine the current variant based on pattern parameters
  defp determine_current_variant(metadata, pattern_params) do
    # Look for variant-determining parameters (like curve_type, illusion_type, etc.)
    variant_params = ["curve_type", "illusion_type", "wave_type", "display_mode"]

    # Find the first variant parameter that exists in the current pattern
    variant_param = Enum.find(variant_params, fn param ->
      Map.has_key?(metadata.parameters, param)
    end)

    if variant_param do
      # Get the current value of the variant parameter
      Map.get(pattern_params, variant_param, "default")
    else
      # Default variant if no variant parameter found
      "default"
    end
  end
end
