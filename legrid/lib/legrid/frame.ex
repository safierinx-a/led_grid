defmodule Legrid.Frame do
  @moduledoc """
  Defines the standard frame format for LED grid data.

  A frame represents a complete snapshot of the LED grid at a point in time.
  """

  defstruct [
    :id,              # Unique identifier for the frame
    :timestamp,       # When the frame was generated
    :source,          # ID of the pattern generator that created this frame
    :width,           # Width of the grid in pixels
    :height,          # Height of the grid in pixels
    :pixels,          # List of pixels in RGB format [r, g, b, r, g, b, ...]
    :metadata         # Optional metadata specific to the pattern generator
  ]

  @type rgb :: {0..255, 0..255, 0..255}

  @type t :: %__MODULE__{
    id: String.t() | nil,
    timestamp: integer() | DateTime.t() | nil,
    source: String.t() | nil,
    width: integer() | nil,
    height: integer() | nil,
    pixels: list({integer(), integer(), integer()}),
    metadata: map() | nil
  }

  @doc """
  Creates a new frame with a unique ID and current timestamp.
  """
  def new(pixels, source \\ nil, metadata \\ %{}) do
    %__MODULE__{
      id: UUID.uuid4(),
      timestamp: DateTime.utc_now(),
      source: source,
      width: nil, # Will be determined by the grid
      height: nil, # Will be determined by the grid
      pixels: pixels,
      metadata: metadata
    }
  end

  @doc """
  Creates a new frame with a specified width and height.
  """
  def new(source, width, height, pixels, metadata \\ %{}) do
    %__MODULE__{
      id: UUID.uuid4(),
      timestamp: DateTime.utc_now(),
      source: source,
      width: width,
      height: height,
      pixels: pixels,
      metadata: metadata
    }
  end

  @doc """
  Converts a frame to a JSON-serializable map.
  """
  def to_json(%__MODULE__{} = frame) do
    %{
      "id" => frame.id || UUID.uuid4(),
      "timestamp" => format_timestamp(frame.timestamp),
      "type" => "frame",
      "width" => frame.width,
      "height" => frame.height,
      "pixels" => serialize_pixels(frame.pixels),
      "source" => frame.source
    }
  end

  @doc """
  Creates a frame from a JSON map.
  """
  def from_json(json) when is_map(json) do
    %__MODULE__{
      id: json["id"],
      timestamp: parse_timestamp(json["timestamp"]),
      source: json["source"],
      width: json["width"],
      height: json["height"],
      pixels: deserialize_pixels(json["pixels"]),
      metadata: json["metadata"] || %{}
    }
  end

  # Helper functions for serializing and deserializing pixels

  defp serialize_pixels(pixels) when is_list(pixels) do
    pixels
    |> Enum.map(fn {r, g, b} -> [r, g, b] end)
    |> List.flatten()
  end

  defp serialize_pixels(pixels) when is_binary(pixels), do: pixels

  defp deserialize_pixels(pixels) when is_list(pixels) do
    pixels
    |> Enum.chunk_every(3)
    |> Enum.map(fn [r, g, b] -> {r, g, b} end)
  end

  defp deserialize_pixels(pixels) when is_binary(pixels), do: pixels

  defp parse_timestamp(nil), do: DateTime.utc_now()
  defp parse_timestamp(timestamp) when is_binary(timestamp) do
    case DateTime.from_iso8601(timestamp) do
      {:ok, datetime, _} -> datetime
      _ -> DateTime.utc_now()
    end
  end

  # Helper to safely format timestamps of different types
  defp format_timestamp(%DateTime{} = dt), do: DateTime.to_iso8601(dt)
  defp format_timestamp(nil), do: DateTime.to_iso8601(DateTime.utc_now())
  defp format_timestamp(timestamp) when is_integer(timestamp) do
    # Convert integer timestamp to DateTime first
    case DateTime.from_unix(div(timestamp, 1000)) do
      {:ok, dt} -> DateTime.to_iso8601(dt)
      _ -> DateTime.to_iso8601(DateTime.utc_now())
    end
  end
  defp format_timestamp(_), do: DateTime.to_iso8601(DateTime.utc_now())
end
