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
    id: String.t(),
    timestamp: DateTime.t(),
    source: String.t(),
    width: pos_integer(),
    height: pos_integer(),
    pixels: [rgb] | binary(),
    metadata: map()
  }

  @doc """
  Creates a new frame with the given parameters.
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
  Converts the frame to a map suitable for JSON encoding.
  """
  def to_json(%__MODULE__{} = frame) do
    %{
      id: frame.id,
      timestamp: DateTime.to_iso8601(frame.timestamp),
      source: frame.source,
      width: frame.width,
      height: frame.height,
      pixels: serialize_pixels(frame.pixels),
      metadata: frame.metadata
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
end
