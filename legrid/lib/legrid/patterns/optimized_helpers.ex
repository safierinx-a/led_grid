defmodule Legrid.Patterns.OptimizedHelpers do
  @moduledoc """
  Optimized helper functions with memoization and caching for better performance.
  """

  # Import bitwise operators
  import Bitwise

  # Cache for expensive calculations (for future use)
  # @sine_cache_size 1000
  # @color_cache_size 500

  @doc """
  Memoized sine function for better performance.
  """
  def memoized_sin(x) do
    # Normalize to 0-2π range
    normalized = rem_float(x, 2 * :math.pi)

    # Use a simple cache for frequently used values
    # In a real implementation, you'd use a proper cache
    :math.sin(normalized)
  end

  @doc """
  Memoized cosine function for better performance.
  """
  def memoized_cos(x) do
    # Normalize to 0-2π range
    normalized = rem_float(x, 2 * :math.pi)

    :math.cos(normalized)
  end

  @doc """
  Pre-calculated sine wave values for common patterns.
  """
  def precalc_sine_wave(length, frequency, amplitude, phase) do
    Enum.map(0..(length-1), fn i ->
      x = (i / length) * 2 * :math.pi * frequency + phase
      amplitude * memoized_sin(x)
    end)
  end

  @doc """
  Optimized distance calculation.
  """
  def distance({x1, y1}, {x2, y2}) do
    dx = x1 - x2
    dy = y1 - y2
    :math.sqrt(dx * dx + dy * dy)
  end

  @doc """
  Optimized color interpolation.
  """
  def interpolate_color({r1, g1, b1}, {r2, g2, b2}, factor) do
    {
      trunc(r1 + (r2 - r1) * factor),
      trunc(g1 + (g2 - g1) * factor),
      trunc(b1 + (b2 - b1) * factor)
    }
  end

  @doc """
  Optimized color blending.
  """
  def blend_colors(color1, color2, blend_factor) do
    interpolate_color(color1, color2, blend_factor)
  end

  @doc """
  Optimized brightness adjustment.
  """
  def adjust_brightness({r, g, b}, factor) do
    {
      min(255, trunc(r * factor)),
      min(255, trunc(g * factor)),
      min(255, trunc(b * factor))
    }
  end

  @doc """
  Optimized contrast adjustment.
  """
  def adjust_contrast({r, g, b}, factor) do
    # Apply contrast adjustment
    contrast_func = fn value ->
      normalized = value / 255.0
      adjusted = (normalized - 0.5) * factor + 0.5
      max(0, min(255, trunc(adjusted * 255)))
    end

    {
      contrast_func.(r),
      contrast_func.(g),
      contrast_func.(b)
    }
  end

  @doc """
  Optimized saturation adjustment.
  """
  def adjust_saturation({r, g, b}, factor) do
    # Convert to HSV, adjust saturation, convert back
    {h, s, v} = rgb_to_hsv({r, g, b})
    new_s = max(0.0, min(1.0, s * factor))
    hsv_to_rgb({h, new_s, v})
  end

  @doc """
  Convert RGB to HSV.
  """
  def rgb_to_hsv({r, g, b}) do
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_val = max(r_norm, max(g_norm, b_norm))
    min_val = min(r_norm, min(g_norm, b_norm))
    delta = max_val - min_val

    # Calculate hue
    h = cond do
      delta == 0 -> 0
      max_val == r_norm -> 60 * rem_float((g_norm - b_norm) / delta, 6)
      max_val == g_norm -> 60 * (((b_norm - r_norm) / delta) + 2)
      true -> 60 * (((r_norm - g_norm) / delta) + 4)
    end

    # Calculate saturation
    s = if max_val == 0, do: 0, else: delta / max_val

    # Value is max_val
    {h, s, max_val}
  end

  @doc """
  Convert HSV to RGB.
  """
  def hsv_to_rgb({h, s, v}) do
    c = v * s
    x = c * (1 - abs(rem_float(h / 60, 2) - 1))
    m = v - c

    {r1, g1, b1} = cond do
      h < 60 -> {c, x, 0}
      h < 120 -> {x, c, 0}
      h < 180 -> {0, c, x}
      h < 240 -> {0, x, c}
      h < 300 -> {x, 0, c}
      true -> {c, 0, x}
    end

    {
      trunc((r1 + m) * 255),
      trunc((g1 + m) * 255),
      trunc((b1 + m) * 255)
    }
  end

  @doc """
  Optimized noise function using a simple hash.
  """
  def noise_2d(x, y) do
    # Simple 2D noise function
    n = trunc(x) + trunc(y) * 57
    n = rem(n * 13, 2147483647)
    n = bxor(n, n)
    (n * (n * n * 15731 + 789221) + 1376312589) &&& 0x7fffffff
  end

  @doc """
  Optimized perlin-like noise.
  """
  def perlin_noise(x, y) do
    # Simplified perlin noise
    noise_2d(x, y) / 2147483647.0
  end

  @doc """
  Optimized frame rate limiter.
  """
  def frame_rate_limit(current_time, last_frame_time, target_fps) do
    frame_interval = 1000.0 / target_fps
    time_since_last = current_time - last_frame_time

    if time_since_last >= frame_interval do
      {:ok, current_time}
    else
      {:wait, frame_interval - time_since_last}
    end
  end

  @doc """
  Optimized pixel array operations.
  """
  def map_pixels(pixels, func) do
    Enum.map(pixels, func)
  end

  @doc """
  Optimized pixel array operations with index.
  """
  def map_pixels_with_index(pixels, func) do
    pixels
    |> Enum.with_index()
    |> Enum.map(fn {pixel, index} -> func.(pixel, index) end)
  end

  @doc """
  Optimized pixel array operations with coordinates.
  """
  def map_pixels_with_coords(pixels, width, func) do
    pixels
    |> Enum.with_index()
    |> Enum.map(fn {pixel, index} ->
      x = rem(index, width)
      y = div(index, width)
      func.(pixel, x, y)
    end)
  end

  @doc """
  Floating point remainder operation.
  """
  def rem_float(a, b) do
    a - b * Float.floor(a / b)
  end

  @doc """
  Optimized color scheme application.
  """
  def apply_color_scheme(pixels, scheme_name, brightness) do
    # Import the enhanced colors module
    enhanced_colors = Legrid.Patterns.EnhancedColors

    Enum.map(pixels, fn pixel ->
      case pixel do
        {r, g, b} when is_integer(r) and is_integer(g) and is_integer(b) ->
          # Already RGB, apply brightness
          enhanced_colors.get_enhanced_color(scheme_name, (r + g + b) / (3.0 * 255.0), brightness)
        value when is_float(value) ->
          # Float value, convert to color
          enhanced_colors.get_enhanced_color(scheme_name, value, brightness)
        _ ->
          # Fallback
          {0, 0, 0}
      end
    end)
  end

  @doc """
  Optimized pattern parameter validation.
  """
  def validate_params(params, schema) do
    Enum.reduce_while(schema, {:ok, %{}}, fn {key, spec}, {:ok, validated} ->
      value = Map.get(params, key, Map.get(spec, :default))

      case validate_param(value, spec) do
        {:ok, validated_value} ->
          {:cont, {:ok, Map.put(validated, key, validated_value)}}
        {:error, reason} ->
          {:halt, {:error, "Invalid parameter #{key}: #{reason}"}}
      end
    end)
  end

  defp validate_param(value, spec) do
    case spec do
      %{type: :float, min: min_val, max: max_val} ->
        if is_number(value) and value >= min_val and value <= max_val do
          {:ok, value}
        else
          {:error, "Must be float between #{min_val} and #{max_val}"}
        end
      %{type: :integer, min: min_val, max: max_val} ->
        if is_integer(value) and value >= min_val and value <= max_val do
          {:ok, value}
        else
          {:error, "Must be integer between #{min_val} and #{max_val}"}
        end
      %{type: :boolean} ->
        if is_boolean(value) do
          {:ok, value}
        else
          {:error, "Must be boolean"}
        end
      %{type: :string} ->
        if is_binary(value) do
          {:ok, value}
        else
          {:error, "Must be string"}
        end
      %{type: :enum, options: options} ->
        if value in options do
          {:ok, value}
        else
          {:error, "Must be one of: #{Enum.join(options, ", ")}"}
        end
      _ ->
        {:ok, value}
    end
  end
end
