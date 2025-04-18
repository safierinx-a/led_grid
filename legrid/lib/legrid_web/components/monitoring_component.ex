defmodule LegridWeb.Components.MonitoringComponent do
  use Phoenix.Component

  attr :stats, :map, required: true
  attr :detailed_stats, :map, default: nil
  attr :stats_history, :list, default: []
  attr :class, :string, default: ""

  def monitoring_panel(assigns) do
    ~H"""
    <div class={"monitoring-panel #{@class}"}>
      <div class="panel-header">
        <h3>
          <span class="material-icons">monitoring</span>
          System Monitoring
        </h3>
        <div class="panel-actions">
          <button phx-click="request_stats" title="Refresh Stats" class="btn-icon">
            <span class="material-icons">refresh</span>
          </button>
          <button phx-click="clear_history" title="Clear History" class="btn-icon">
            <span class="material-icons">clear_all</span>
          </button>
        </div>
      </div>

      <div class="stats-overview">
        <div class="stat-card">
          <div class="stat-value"><%= @stats.fps %></div>
          <div class="stat-label">FPS</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.frames_received %></div>
          <div class="stat-label">Frames</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.frames_dropped %></div>
          <div class="stat-label">Dropped</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= format_bandwidth(@stats.bandwidth_in) %></div>
          <div class="stat-label">IN</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= format_bandwidth(@stats.bandwidth_out) %></div>
          <div class="stat-label">OUT</div>
        </div>

        <div class="stat-card">
          <div class="stat-value"><%= @stats.clients %></div>
          <div class="stat-label">Clients</div>
        </div>
      </div>

      <%= if @detailed_stats do %>
        <div class="stats-details">
          <div class="stat-section">
            <h4>System</h4>
            <div class="stat-row">
              <div class="stat-name">Uptime:</div>
              <div class="stat-value"><%= format_duration(get_in(@detailed_stats, [:system, "uptime"])) %></div>
            </div>
            <div class="stat-row">
              <div class="stat-name">RSS Memory:</div>
              <div class="stat-value"><%= format_bytes(get_in(@detailed_stats, [:system, "memory", "rss"])) %></div>
            </div>
            <div class="stat-row">
              <div class="stat-name">Heap Memory:</div>
              <div class="stat-value"><%= format_bytes(get_in(@detailed_stats, [:system, "memory", "heapTotal"])) %></div>
            </div>
          </div>

          <div class="stat-section">
            <h4>Performance</h4>
            <div class="stat-row">
              <div class="stat-name">Total Received:</div>
              <div class="stat-value"><%= format_bytes(get_in(@detailed_stats, [:performance, "bytes_received"])) %></div>
            </div>
            <div class="stat-row">
              <div class="stat-name">Total Sent:</div>
              <div class="stat-value"><%= format_bytes(get_in(@detailed_stats, [:performance, "bytes_sent"])) %></div>
            </div>
          </div>

          <%= if get_in(@detailed_stats, [:buffer]) do %>
            <div class="stat-section">
              <h4>Frame Buffer</h4>
              <div class="stat-row">
                <div class="stat-name">Fullness:</div>
                <div class="stat-value"><%= format_percentage(get_in(@detailed_stats, [:buffer, "fullness"])) %></div>
              </div>
              <div class="stat-row">
                <div class="stat-name">FPS:</div>
                <div class="stat-value"><%= format_number(get_in(@detailed_stats, [:buffer, "fps"])) %> fps</div>
              </div>
              <div class="stat-row">
                <div class="stat-name">Queue:</div>
                <div class="stat-value"><%= get_in(@detailed_stats, [:buffer, "queue_length"]) || 0 %> frames</div>
              </div>
            </div>
          <% end %>

          <%= if get_in(@detailed_stats, [:buffer_status]) do %>
            <div class="stat-section">
              <h4>Server Buffer</h4>
              <div class="stat-row">
                <div class="stat-name">Frames In Buffer:</div>
                <div class="stat-value"><%= get_in(@detailed_stats, [:buffer_status, :frames_in_buffer]) || 0 %></div>
              </div>
              <div class="stat-row">
                <div class="stat-name">Batch Size:</div>
                <div class="stat-value"><%= get_in(@detailed_stats, [:buffer_status, :batch_size]) || 0 %> frames</div>
              </div>
              <div class="stat-row">
                <div class="stat-name">Batches Sent:</div>
                <div class="stat-value"><%= get_in(@detailed_stats, [:buffer_status, :batches_sent]) || 0 %></div>
              </div>
            </div>
          <% end %>
        </div>
      <% end %>

      <div class="simulation-controls">
        <h4>Network Simulation</h4>
        <div class="simulation-options">
          <label class="simulation-option">
            <input type="checkbox" phx-click="simulate_latency" phx-value-enabled="true" />
            <span>Simulate Latency</span>
          </label>
          <label class="simulation-option">
            <input type="checkbox" phx-click="simulate_packet_loss" phx-value-enabled="true" />
            <span>Simulate Packet Loss</span>
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
