defmodule LegridWeb.HomeLive do
  use LegridWeb, :live_view

  alias Legrid.Patterns.{Registry, Runner}
  alias Legrid.Controller.Interface

  import LegridWeb.Components.MonitoringComponent

  @grid_width 25
  @grid_height 24
  @pixel_size 20 # Size of each LED in the web interface

  @impl true
  def mount(_params, _session, socket) do
    # Subscribe to frame updates and controller stats
    if connected?(socket) do
      Runner.subscribe()
      Phoenix.PubSub.subscribe(Legrid.PubSub, "controller_stats")
      # Attempt to activate monitoring safely
      try do
        Interface.activate_monitor()
        # Request stats immediately
        request_stats()
      rescue
        _ -> :ok # Silently handle errors if the controller isn't available
      end
    end

    # Get available patterns
    patterns = Registry.list_patterns()

    # Attempt to get controller status safely
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
    |> assign(:monitoring_active, true) # Start with monitoring active
    |> assign(:controller_enabled, true) # Start with controller enabled

    {:ok, socket}
  end

  @impl true
  def terminate(_reason, _socket) do
    # Safely deactivate monitoring when this page is unmounted
    try do
      Interface.deactivate_monitor()
    rescue
      _ -> :ok # Silently handle errors if the controller isn't available
    end
    :ok
  end

  @impl true
  def handle_event("select-pattern", %{"pattern_id" => pattern_id}, socket) do
    try do
      case Registry.get_pattern(pattern_id) do
        {:ok, metadata} ->
          # Extract default params
          default_params = metadata.parameters
          |> Enum.map(fn {key, param} -> {key, param.default} end)
          |> Enum.into(%{})

          # First update the socket
          socket = assign(socket,
            pattern_params: default_params,
            current_pattern: pattern_id,
            pattern_metadata: metadata
          )

          # Then attempt to start pattern if controller enabled
          # Do this after socket is already updated to prevent UI lockup
          if socket.assigns.controller_enabled do
            try do
              Runner.start_pattern(pattern_id, default_params)
            rescue
              error ->
                IO.inspect(error, label: "Error starting pattern")
                # Continue even if pattern start fails
            end
          end

          {:noreply, socket}

        {:error, reason} ->
          IO.inspect(reason, label: "Pattern load error")
          {:noreply, socket}
      end
    rescue
      error ->
        IO.inspect(error, label: "Error in select-pattern")
        {:noreply, socket}
    end
  end

  @impl true
  def handle_event("update-form-params", %{"params" => params} = form_params, socket) do
    pattern_id = socket.assigns.current_pattern

    if pattern_id do
      try do
        {:ok, metadata} = Registry.get_pattern(pattern_id)

        # Convert parameter values to appropriate types
        converted_params = Enum.reduce(params, %{}, fn {key, value}, acc ->
          param_def = metadata.parameters[key]
          if param_def do
            # Convert value to appropriate type - add error handling
            try do
              converted_value = convert_param_value(value, param_def.type)
              Map.put(acc, key, converted_value)
            rescue
              _ -> acc # If conversion fails, skip this parameter
            end
          else
            acc
          end
        end)

        # Update the socket with new parameters
        pattern_params = Map.merge(socket.assigns.pattern_params, converted_params)

        # Apply if controller enabled - auto-apply changes
        if socket.assigns.controller_enabled do
          Runner.update_pattern_params(pattern_params)
        end

        {:noreply, assign(socket, pattern_params: pattern_params)}
      rescue
        error ->
          IO.inspect(error, label: "Error in update-form-params")
          {:noreply, socket}  # Return unchanged socket on error
      end
    else
      {:noreply, socket}
    end
  end

  @impl true
  def handle_event("update-param", %{"value" => value, "_target" => [key]}, socket) do
    # Handle direct value change
    IO.puts("Processing parameter update for #{key} = #{value}")

    # Get parameter definition
    pattern_id = socket.assigns.current_pattern
    {:ok, metadata} = Registry.get_pattern(pattern_id)
    param_def = metadata.parameters[key]

    if param_def do
      # Convert based on parameter type
      converted_value = convert_param_value(value, param_def.type)

      # Update the parameter
      pattern_params = Map.put(socket.assigns.pattern_params, key, converted_value)

      # Apply if controller enabled
      if socket.assigns.controller_enabled do
        Runner.update_pattern_params(pattern_params)
      end

      {:noreply, assign(socket, pattern_params: pattern_params)}
    else
      # Parameter not found - possibly a checkbox which doesn't use value
      IO.puts("Parameter definition not found for direct update: #{key}")
      {:noreply, socket}
    end
  end

  @impl true
  def handle_event("update-param", %{"_target" => [key]} = params, socket) do
    # This handles checkbox inputs which send true/false directly
    value = params[key]
    IO.puts("Processing parameter update for #{key} = #{inspect(value)}")

    # Get parameter definition
    pattern_id = socket.assigns.current_pattern
    {:ok, metadata} = Registry.get_pattern(pattern_id)
    param_def = metadata.parameters[key]

    if param_def do
      # Convert based on parameter type
      converted_value = convert_param_value(value, param_def.type)

      # Update the parameter
      pattern_params = Map.put(socket.assigns.pattern_params, key, converted_value)

      # Apply if controller enabled
      if socket.assigns.controller_enabled do
        Runner.update_pattern_params(pattern_params)
      end

      {:noreply, assign(socket, pattern_params: pattern_params)}
    else
      IO.puts("Parameter definition not found for: #{key}")
      {:noreply, socket}
    end
  end

  @impl true
  def handle_event("update-param", params, socket) do
    # This is a fallback handler for any other format
    IO.inspect(params, label: "Fallback parameter update")

    # Extract the field that was updated
    case params["_target"] do
      [key] ->
        value = params[key]

        # Get parameter definition
        pattern_id = socket.assigns.current_pattern
        {:ok, metadata} = Registry.get_pattern(pattern_id)
        param_def = metadata.parameters[key]

        if param_def do
          # Convert value
          converted_value = convert_param_value(value, param_def.type)

          # Update parameter
          pattern_params = Map.put(socket.assigns.pattern_params, key, converted_value)

          # Apply if controller enabled
          if socket.assigns.controller_enabled do
            Runner.update_pattern_params(pattern_params)
          end

          {:noreply, assign(socket, pattern_params: pattern_params)}
        else
          IO.puts("Parameter definition not found: #{key}")
          {:noreply, socket}
        end

      _ ->
        IO.puts("Could not determine parameter from: #{inspect(params)}")
        {:noreply, socket}
    end
  end

  @impl true
  def handle_event("stop-pattern", _params, socket) do
    try do
      Runner.stop_pattern()
    rescue
      error -> IO.inspect(error, label: "Error stopping pattern")
    end
    {:noreply, socket}
  end

  @impl true
  def handle_event("toggle-controller", _params, socket) do
    new_state = !socket.assigns.controller_enabled

    if new_state do
      # Re-enable controller
      if socket.assigns.current_pattern do
        # Restart the current pattern if one is selected
        try do
          Runner.start_pattern(socket.assigns.current_pattern, socket.assigns.pattern_params)
        rescue
          error -> IO.inspect(error, label: "Error re-enabling controller")
        end
      end
    else
      # Disable controller - stop any running pattern
      try do
        Runner.stop_pattern()
      rescue
        error -> IO.inspect(error, label: "Error stopping pattern on disable")
      end
    end

    {:noreply, assign(socket, controller_enabled: new_state)}
  end

  @impl true
  def handle_event("clear-frame", _params, socket) do
    # Send a blank frame to reset all LEDs
    Runner.clear_frame()
    {:noreply, socket}
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
  def handle_event("update-param-direct", params, socket) do
    # This is a simpler event handler that handles a single parameter change directly
    IO.inspect(params, label: "Direct parameter update")

    # Get the parameter key and value
    param_key = params["param"]
    param_value = params[param_key]

    if param_key && param_value do
      # Get param definition for type conversion
      pattern_id = socket.assigns.current_pattern
      {:ok, metadata} = Registry.get_pattern(pattern_id)
      param_def = metadata.parameters[param_key]

      if param_def do
        # Convert value based on parameter type
        converted_value = convert_param_value(param_value, param_def.type)

        # Update the parameter value in the pattern params
        pattern_params = Map.put(socket.assigns.pattern_params, param_key, converted_value)

        # Apply parameter changes if the controller is enabled
        if socket.assigns.controller_enabled do
          Runner.update_pattern_params(pattern_params)
        end

        # Update the UI
        {:noreply, assign(socket, pattern_params: pattern_params)}
      else
        # Parameter definition not found, just log and return
        IO.puts("Parameter definition not found for #{param_key}")
        {:noreply, socket}
      end
    else
      # Couldn't determine the parameter, just log and return
      IO.puts("Could not determine parameter from event: #{inspect(params)}")
      {:noreply, socket}
    end
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
end
