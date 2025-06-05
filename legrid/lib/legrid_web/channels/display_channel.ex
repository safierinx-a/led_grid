defmodule LegridWeb.DisplayChannel do
  @moduledoc """
  High-performance channel for streaming LED frame data directly to browsers.

  This channel handles only frame streaming, keeping it separate from
  LiveView UI state management for optimal performance.
  """

  use Phoenix.Channel
  require Logger

  @impl true
  def join("display:grid", _payload, socket) do
    Logger.info("Display client connected for LED grid streaming")

    # Subscribe to frame updates
    Phoenix.PubSub.subscribe(Legrid.PubSub, "frames")

    # Send current frame immediately if available
    try do
      case Legrid.Patterns.Runner.current_pattern() do
        {:ok, pattern_info} ->
          # Send pattern info to client
          push(socket, "pattern_active", %{
            pattern_id: pattern_info.id,
            params: pattern_info.params
          })
        _ -> :ok
      end
    rescue
      _ -> :ok
    end

    {:ok, socket}
  end

  @impl true
  def handle_info({:frame, frame}, socket) do
    # Stream frame data efficiently
    frame_data = %{
      pixels: encode_pixels_efficiently(frame.pixels),
      timestamp: System.system_time(:millisecond),
      pattern_id: get_in(frame.metadata, ["pattern_id"])
    }

    push(socket, "frame_update", frame_data)
    {:noreply, socket}
  end

  @impl true
  def handle_info({:pattern_changed, pattern_id, params}, socket) do
    # Notify client of pattern changes
    push(socket, "pattern_changed", %{
      pattern_id: pattern_id,
      params: params
    })
    {:noreply, socket}
  end

  # Efficient pixel encoding - flatten RGB tuples to array
  defp encode_pixels_efficiently(pixels) when is_list(pixels) do
    pixels
    |> Enum.flat_map(fn {r, g, b} -> [r, g, b] end)
  end

  # Handle case where pixels might be in different format
  defp encode_pixels_efficiently(pixels), do: pixels
end
