defmodule LegridWeb.Components.MonitoringComponent do
  use Phoenix.Component

  attr :stats, :map, required: true
  attr :detailed_stats, :map, default: nil
  attr :stats_history, :list, default: []
  attr :class, :string, default: ""

  def monitoring_panel(assigns) do
    ~H"""
    <div class={"stats-panel #{@class}"}>
      <div class="stats-header">
        <h2>
          <span class="material-icons">monitoring</span>
          System Monitoring
        </h2>
        <div class="stats-actions">
          <button phx-click="request_stats" class="icon-btn" title="Refresh">
            <span class="material-icons">refresh</span>
          </button>
          <button phx-click="clear_history" class="icon-btn" title="Clear History">
            <span class="material-icons">delete_sweep</span>
          </button>
        </div>
      </div>

      <div class="stats-cards">
        <div class="stat-card highlight">
          <div class="stat-value"><%= @stats.fps %></div>
          <div class="stat-label">FPS</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.frames_received %></div>
          <div class="stat-label">Frames</div>
        </div>

        <div class={["stat-card", @stats.frames_dropped > 0 && "danger"]}>
          <div class="stat-value"><%= @stats.frames_dropped %></div>
          <div class="stat-label">Dropped</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.bandwidth_in %></div>
          <div class="stat-label">IN B/s</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.bandwidth_out %></div>
          <div class="stat-label">OUT B/s</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.clients %></div>
          <div class="stat-label">Clients</div>
        </div>
      </div>

      <%= if @detailed_stats do %>
        <div class="stats-details">
          <div class="detail-section">
            <h3><span class="material-icons">memory</span> System</h3>
            <div class="detail-row">
              <div class="detail-label">Uptime:</div>
              <div class="detail-value"><%= format_duration(get_in(@detailed_stats, [:system, "uptime"])) %></div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Memory:</div>
              <div class="detail-value"><%= format_bytes(get_in(@detailed_stats, [:system, "memory", "rss"])) %></div>
            </div>
          </div>

          <div class="detail-section">
            <h3><span class="material-icons">lan</span> Network</h3>
            <div class="detail-row">
              <div class="detail-label">Total Received:</div>
              <div class="detail-value"><%= format_bytes(get_in(@detailed_stats, [:performance, "bytes_received"])) %></div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Total Sent:</div>
              <div class="detail-value"><%= format_bytes(get_in(@detailed_stats, [:performance, "bytes_sent"])) %></div>
            </div>
          </div>
        </div>
      <% end %>

      <div class="network-simulation">
        <h3><span class="material-icons">science</span> Network Simulation</h3>
        <div class="simulation-options">
          <label class="toggle-option">
            <span>Simulate Latency</span>
            <label class="toggle-switch">
              <input type="checkbox" phx-click="simulate_latency" phx-value-enabled="true" />
              <span class="toggle-slider"></span>
            </label>
          </label>

          <label class="toggle-option">
            <span>Simulate Packet Loss</span>
            <label class="toggle-switch">
              <input type="checkbox" phx-click="simulate_packet_loss" phx-value-enabled="true" />
              <span class="toggle-slider"></span>
            </label>
          </label>
        </div>
      </div>
    </div>
    """
  end

  # Format bytes to human-readable
  defp format_bytes(bytes) when is_integer(bytes) do
    cond do
      bytes >= 1_000_000_000 -> "#{Float.round(bytes / 1_000_000_000, 2)} GB"
      bytes >= 1_000_000 -> "#{Float.round(bytes / 1_000_000, 2)} MB"
      bytes >= 1_000 -> "#{Float.round(bytes / 1_000, 2)} KB"
      true -> "#{bytes} B"
    end
  end
  defp format_bytes(_), do: "0 B"

  # Format duration in seconds to human-readable
  defp format_duration(seconds) when is_integer(seconds) do
    hours = div(seconds, 3600)
    minutes = div(rem(seconds, 3600), 60)
    secs = rem(seconds, 60)

    cond do
      hours > 0 -> "#{hours}h #{minutes}m #{secs}s"
      minutes > 0 -> "#{minutes}m #{secs}s"
      true -> "#{secs}s"
    end
  end
  defp format_duration(_), do: "0s"

  # Format bandwidth (bytes per second) to human-readable
  defp format_bandwidth(bytes_per_sec) when is_integer(bytes_per_sec) do
    "#{format_bytes(bytes_per_sec)}/s"
  end
  defp format_bandwidth(_), do: "0 B/s"

  # Format a percentage value
  defp format_percentage(value) when is_number(value) do
    "#{Float.round(value * 100, 1)}%"
  end
  defp format_percentage(_), do: "0%"

  # Format a number with 1 decimal place
  defp format_number(value) when is_number(value) do
    Float.round(value, 1)
  end
  defp format_number(_), do: 0.0
end
