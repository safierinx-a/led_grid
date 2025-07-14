defmodule LegridWeb.GridControlLive do
  use LegridWeb, :live_view

  alias Legrid.Patterns.{Registry, Runner}
  alias Legrid.Controller.Interface
  alias Phoenix.PubSub

  @grid_width 25
  @grid_height 24
  @pixel_size 20

  def mount(_params, _session, socket) do
    # Connect to all necessary PubSub topics when the LiveView connects
    if connected?(socket) do
      PubSub.subscribe(Legrid.PubSub, "frames")
      PubSub.subscribe(Legrid.PubSub, "controller_stats")
      PubSub.subscribe(Legrid.PubSub, "pattern_updates")

      # Initialize monitoring
      try do
        Interface.activate_monitor()
      rescue
        _ -> :ok
      end
    end

    # Get available patterns
    patterns = Registry.list_patterns()

    # Get controller status
    controller_status = try do
      Interface.status()
    rescue
      _ -> %{connected: false, url: nil, width: @grid_width, height: @grid_height}
    end

    # Get current pattern if running
    current_pattern_info = try do
      case Runner.current_pattern() do
        {:ok, info} -> %{
          id: info.id,
          params: info.params
        }
        _ -> nil
      end
    rescue
      _ -> nil
    end

    # Load pattern metadata if we have an active pattern
    {pattern_id, pattern_meta, pattern_params} = if current_pattern_info do
      case Registry.get_pattern(current_pattern_info.id) do
        {:ok, meta} ->
          # Merge default params with current params
          defaults = meta.parameters
                    |> Enum.map(fn {k, p} -> {k, p.default} end)
                    |> Enum.into(%{})
          merged_params = Map.merge(defaults, current_pattern_info.params)
          {current_pattern_info.id, meta, merged_params}
        _ -> {nil, nil, %{}}
      end
    else
      {nil, nil, %{}}
    end

    # Initialize socket with all required state
    socket = socket
      |> assign(:patterns, patterns)
      |> assign(:current_pattern, pattern_id)
      |> assign(:pattern_metadata, pattern_meta)
      |> assign(:pattern_params, pattern_params)
      |> assign(:pixels, blank_pixels(@grid_width, @grid_height))
      |> assign(:controller_status, controller_status)
      |> assign(:grid_width, @grid_width)
      |> assign(:grid_height, @grid_height)
      |> assign(:pixel_size, @pixel_size)
      |> assign(:controller_enabled, true)
      |> assign(:show_stats, false)
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

    if pattern_id && connected?(socket) do
      # Immediately notify client of current pattern
      socket = push_event(socket, "pattern_changed", %{pattern_id: pattern_id})
    end

    {:ok, socket}
  end

  def render(assigns) do
    ~H"""
    <div id="grid-dashboard" class="grid-dashboard" phx-hook="GridControl">
      <header class="dashboard-header">
        <div class="logo">
          <div class="logo-icon">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="2" y="2" width="5" height="5" rx="1" fill="currentColor"/>
              <rect x="9" y="2" width="5" height="5" rx="1" fill="currentColor"/>
              <rect x="2" y="9" width="5" height="5" rx="1" fill="currentColor"/>
              <rect x="9" y="9" width="5" height="5" rx="1" fill="currentColor"/>
            </svg>
          </div>
          <span>Legrid Controller</span>
        </div>

        <div class={"connection-status #{if @controller_status.connected, do: "connected", else: "disconnected"}"}>
          <div class="status-indicator"></div>
          <span><%= if @controller_status.connected, do: "Connected", else: "Disconnected" %></span>
        </div>

        <div class="controls">
          <button class={"control-btn #{if @controller_enabled, do: "active"}"} phx-click="toggle-power">
            <span class="icon">⏻</span>
          </button>
          <button class="control-btn" phx-click="clear-display">
            <span class="icon">⌫</span>
          </button>
          <button class={"control-btn #{if @show_stats, do: "active"}"} phx-click="toggle-stats">
            <span class="icon">📊</span>
          </button>
        </div>
      </header>

      <div class="dashboard-content">
        <div class="patterns-panel">
          <h2>Patterns</h2>
          <div class="pattern-list">
            <%= for pattern <- @patterns do %>
              <div
                class={"pattern-item #{if @current_pattern == pattern.id, do: "active"}"}
                phx-click="select-pattern"
                phx-value-pattern_id={pattern.id}
              >
                <h3><%= pattern.name %></h3>
                <p><%= pattern.description %></p>
              </div>
            <% end %>
          </div>
        </div>

        <div class="main-display">
          <div class="grid-container" style={"width: #{@grid_width * @pixel_size}px; height: #{@grid_height * @pixel_size}px;"}>
            <%= for {{r, g, b}, index} <- Enum.with_index(@pixels) do %>
              <%
                x = rem(index, @grid_width)
                y = div(index, @grid_width)
                left = x * @pixel_size
                top = y * @pixel_size
                color = "rgb(#{r}, #{g}, #{b})"

                # Calculate brightness for effects
                brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                is_active = brightness > 0.03

                # Visual effects
                glow_size = if brightness > 0.3, do: brightness * 30, else: 0
                glow_style = if glow_size > 0, do: "0 0 #{glow_size}px rgba(#{r},#{g},#{b},#{brightness * 0.9})", else: "none"
                border_color = if brightness > 0.12, do: "rgba(255,255,255,#{brightness * 0.12})", else: "rgba(0,0,0,0.3)"
              %>
              <div class={"led-pixel #{if is_active, do: "active"}"}
                   style={"left: #{left}px; top: #{top}px; background-color: #{color}; box-shadow: #{glow_style}; border-color: #{border_color};"}
                   data-x={x} data-y={y} data-rgb="#{r},#{g},#{b}">
              </div>
            <% end %>
          </div>

          <%= if @show_stats do %>
            <div id="stats-panel" class="stats-panel">
              <div class="stats-row">
                <div class="stat-item">
                  <div class="stat-label">FPS</div>
                  <div class="stat-value"><%= @stats.fps %></div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">Frames</div>
                  <div class="stat-value"><%= @stats.frames_received %></div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">Dropped</div>
                  <div class="stat-value"><%= @stats.frames_dropped %></div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">Clients</div>
                  <div class="stat-value"><%= @stats.clients %></div>
                </div>
              </div>
            </div>
          <% end %>
        </div>

        <div class="parameters-panel">
          <%= if @current_pattern && @pattern_metadata do %>
            <div class="panel-header">
              <h2>Parameters</h2>
              <button class="stop-btn" phx-click="stop-pattern">Stop</button>
            </div>
            <div id="parameter-controls" data-pattern-id={@current_pattern} phx-hook="ParameterControls">
              <%= for {key, param} <- filter_visible_parameters(@pattern_metadata, @pattern_params) do %>
                <div class="parameter-item" data-param-key={key} data-param-type={param.type} data-param-default={param.default}>
                  <div class="param-header">
                    <label for={key}><%= key %></label>
                    <span class="param-value" id={"display-#{key}"}><%= Map.get(@pattern_params, key, param.default) %></span>
                  </div>
                  <p class="param-desc"><%= param.description %></p>

                  <%= case param.type do %>
                    <% :integer -> %>
                      <div class="slider-container">
                        <input type="range" id={key} name={key} class="slider responsive-control"
                               min={param.min} max={param.max} step="1"
                               value={Map.get(@pattern_params, key, param.default)}
                               data-param-type="integer" />
                      </div>

                    <% :float -> %>
                      <div class="slider-container">
                        <input type="range" id={key} name={key} class="slider responsive-control"
                               min={param.min} max={param.max} step="0.01"
                               value={Map.get(@pattern_params, key, param.default)}
                               data-param-type="float" />
                      </div>

                    <% :boolean -> %>
                      <label class="toggle-switch">
                        <input type="checkbox" id={key} name={key} class="responsive-control"
                               checked={Map.get(@pattern_params, key, param.default)}
                               data-param-type="boolean" />
                        <span class="toggle-slider"></span>
                      </label>

                    <% :string -> %>
                      <input type="text" id={key} name={key} class="text-input responsive-control"
                             value={Map.get(@pattern_params, key, param.default)}
                             data-param-type="string" />

                    <% :enum -> %>
                      <select id={key} name={key} class="select-input responsive-control" data-param-type="enum">
                        <%= for option <- param.options do %>
                          <option value={option} selected={Map.get(@pattern_params, key, param.default) == option}>
                            <%= option %>
                          </option>
                        <% end %>
                      </select>
                  <% end %>
                </div>
              <% end %>
            </div>
          <% else %>
            <div class="no-pattern">
              <p>Select a pattern to see parameters</p>
            </div>
          <% end %>
        </div>
      </div>
    </div>
    """
  end

  # Event Handlers

  def handle_event("select-pattern", %{"pattern_id" => pattern_id}, socket) do
    case Registry.get_pattern(pattern_id) do
      {:ok, metadata} ->
        # Quick parameter setup - optimize this for speed
        default_params = for {key, param} <- metadata.parameters, into: %{} do
          {key, param.default}
        end

        # Simplified parameter preservation for common settings
        preserved_params = if socket.assigns.current_pattern do
          # Only preserve these common parameters quickly
          for key <- ["brightness", "color_scheme", "speed"],
              Map.has_key?(metadata.parameters, key),
              Map.has_key?(socket.assigns.pattern_params, key),
              into: %{} do
            {key, socket.assigns.pattern_params[key]}
          end
        else
          %{}
        end

        # Fast merge
        params = Map.merge(default_params, preserved_params)

        # Update socket immediately for instant UI feedback
        socket = socket
          |> assign(:current_pattern, pattern_id)
          |> assign(:pattern_metadata, metadata)
          |> assign(:pattern_params, params)
          |> push_event("pattern_changed", %{pattern_id: pattern_id})

        # Start pattern asynchronously to prevent UI blocking
        if socket.assigns.controller_enabled do
          # Use Task.start to make this completely non-blocking
          Task.start(fn ->
            try do
              Runner.start_pattern(pattern_id, params)
            rescue
              e ->
                # Log error but don't crash
                IO.inspect(e, label: "Error starting pattern #{pattern_id}")
            end
          end)
        end

        {:noreply, socket}

      {:error, _} ->
        {:noreply, socket}
    end
  end

  def handle_event("batch-param-update", %{"params" => params}, socket) do
    # Simple, reliable parameter update handler
    if socket.assigns.current_pattern && socket.assigns.controller_enabled && map_size(params) > 0 do
      # Update local params for UI responsiveness
      updated_params = Map.merge(socket.assigns.pattern_params, params)

      # Send to pattern runner asynchronously
      Runner.update_pattern_params_immediate(params)

      {:noreply, assign(socket, :pattern_params, updated_params)}
    else
      {:noreply, socket}
    end
  end

  def handle_event("toggle-power", _, socket) do
    enabled = !socket.assigns.controller_enabled

    if enabled do
      # Re-enable and restart current pattern if any
      if socket.assigns.current_pattern do
        try do
          Runner.start_pattern(socket.assigns.current_pattern, socket.assigns.pattern_params)
        rescue
          _ -> :ok
        end
      end
    else
      # Disable by stopping any running pattern
      try do
        Runner.stop_pattern()
      rescue
        _ -> :ok
      end
    end

    {:noreply, assign(socket, :controller_enabled, enabled)}
  end

  def handle_event("clear-display", _, socket) do
    try do
      Runner.clear_frame()
    rescue
      _ -> :ok
    end

    {:noreply, socket}
  end

  def handle_event("stop-pattern", _, socket) do
    try do
      Runner.stop_pattern()
    rescue
      _ -> :ok
    end

    {:noreply, assign(socket, :current_pattern, nil)}
  end

  def handle_event("toggle-stats", _, socket) do
    show_stats = !socket.assigns.show_stats

    # Activate/deactivate detailed monitoring
    if show_stats do
      try do
        Interface.activate_monitor()
        # Request stats immediately
        request_stats()
      rescue
        _ -> :ok
      end
    else
      try do
        Interface.deactivate_monitor()
      rescue
        _ -> :ok
      end
    end

    {:noreply, assign(socket, :show_stats, show_stats)}
  end

  # PubSub Event Handlers

  def handle_info({:frame, frame}, socket) do
    # Extract pixels from the frame and update socket
    {:noreply, assign(socket, :pixels, frame.pixels)}
  end

  def handle_info({:controller_stats, stats}, socket) do
    # Basic stats update
    new_stats = %{
      fps: stats["fps"] || 0,
      frames_received: stats["frames_received"] || 0,
      frames_dropped: stats["frames_dropped"] || 0,
      bandwidth_in: get_in(stats, ["bandwidth", "in"]) || 0,
      bandwidth_out: get_in(stats, ["bandwidth", "out"]) || 0,
      clients: socket.assigns.stats.clients,
      last_updated: System.system_time(:second)
    }

    # Add to history (keep limited history)
    history = [new_stats | socket.assigns.stats_history]
      |> Enum.take(60)

    {:noreply, assign(socket, stats: new_stats, stats_history: history)}
  end

  def handle_info({:controller_stats_detailed, stats}, socket) do
    detailed = %{
      system: stats["system"] || %{},
      performance: stats["performance"] || %{},
      client: stats["client"] || %{}
    }

    # Update client count
    new_stats = Map.put(socket.assigns.stats, :clients, get_in(detailed, [:system, "clients"]) || 0)

    {:noreply, assign(socket, detailed_stats: detailed, stats: new_stats)}
  end

  def handle_info({:pattern_changed, pattern_id, params}, socket) do
    # Update when pattern is changed from elsewhere (e.g., another browser tab)
    case Registry.get_pattern(pattern_id) do
      {:ok, metadata} ->
        # Get default parameters
        default_params = metadata.parameters
          |> Enum.map(fn {k, p} -> {k, p.default} end)
          |> Enum.into(%{})

        # Merge with received params
        merged_params = if is_map(params) && map_size(params) > 0 do
          Map.merge(default_params, params)
        else
          default_params
        end

        # Update the socket with the new pattern and parameters
        socket = socket
          |> assign(:current_pattern, pattern_id)
          |> assign(:pattern_metadata, metadata)
          |> assign(:pattern_params, merged_params)
          |> push_event("pattern_changed", %{pattern_id: pattern_id})

        {:noreply, socket}

      {:error, _} ->
        {:noreply, socket}
    end
  end

  # Helper Functions

  defp blank_pixels(width, height) do
    for _y <- 0..(height - 1), _x <- 0..(width - 1), do: {0, 0, 0}
  end

  defp request_stats do
    try do
      if connected_status = Interface.status() do
        if connected_status.connected && function_exported?(Interface, :request_stats, 0) do
          Interface.request_stats()
        end
      end
    rescue
      _ -> :ok
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
