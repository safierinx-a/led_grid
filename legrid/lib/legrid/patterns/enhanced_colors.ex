defmodule Legrid.Patterns.EnhancedColors do
  @moduledoc """
  Enhanced color utilities with gamma correction and improved color schemes.
  """

  # Gamma correction value for LED displays (typically 2.2-2.4)
  @gamma 2.2

  @doc """
  Apply gamma correction to a color value (0.0 to 1.0).
  This improves color accuracy on LED displays.
  """
  def gamma_correct(value) when is_float(value) and value >= 0.0 and value <= 1.0 do
    :math.pow(value, 1.0 / @gamma)
  end

  def gamma_correct(value) when is_integer(value) and value >= 0 and value <= 255 do
    normalized = value / 255.0
    corrected = gamma_correct(normalized)
    trunc(corrected * 255)
  end

  @doc """
  Apply gamma correction to an RGB tuple.
  """
  def gamma_correct_rgb({r, g, b}) do
    {
      gamma_correct(r),
      gamma_correct(g),
      gamma_correct(b)
    }
  end

  @doc """
  Enhanced color schemes with better visual quality.
  """
  def enhanced_color_schemes do
    %{
      "enhanced_rainbow" => fn value, brightness ->
        # Improved rainbow with better color transitions
        hue = value * 360.0
        rgb = hsv_to_rgb(hue, 1.0, brightness)
        gamma_correct_rgb(rgb)
      end,

      "enhanced_fire" => fn value, brightness ->
        # Enhanced fire effect with better orange/red balance
        r = min(255, trunc(255 * brightness * (1.0 + value * 0.5)))
        g = min(255, trunc(100 * brightness * value))
        b = min(255, trunc(20 * brightness * value * value))
        gamma_correct_rgb({r, g, b})
      end,

      "enhanced_ocean" => fn value, brightness ->
        # Enhanced ocean with better blue/cyan balance
        r = min(255, trunc(20 * brightness * value))
        g = min(255, trunc(150 * brightness * (0.3 + value * 0.7)))
        b = min(255, trunc(255 * brightness * (0.5 + value * 0.5)))
        gamma_correct_rgb({r, g, b})
      end,

      "enhanced_sunset" => fn value, brightness ->
        # Enhanced sunset with better orange/pink balance
        r = min(255, trunc(255 * brightness * (0.7 + value * 0.3)))
        g = min(255, trunc(100 * brightness * value))
        b = min(255, trunc(50 * brightness * value * value))
        gamma_correct_rgb({r, g, b})
      end,

      "enhanced_forest" => fn value, brightness ->
        # Enhanced forest with better green balance
        r = min(255, trunc(50 * brightness * value))
        g = min(255, trunc(200 * brightness * (0.4 + value * 0.6)))
        b = min(255, trunc(30 * brightness * value))
        gamma_correct_rgb({r, g, b})
      end,

      "enhanced_neon" => fn value, brightness ->
        # Enhanced neon with better saturation
        hue = value * 360.0
        rgb = hsv_to_rgb(hue, 1.0, brightness * 1.2)
        gamma_correct_rgb(rgb)
      end,

      "enhanced_pastel" => fn value, brightness ->
        # Enhanced pastel with softer colors
        hue = value * 360.0
        rgb = hsv_to_rgb(hue, 0.6, brightness * 0.8)
        gamma_correct_rgb(rgb)
      end,

      "enhanced_monochrome" => fn value, brightness ->
        # Enhanced monochrome with better contrast
        intensity = trunc(255 * brightness * value)
        gamma_correct_rgb({intensity, intensity, intensity})
      end
    }
  end

  @doc """
  Convert HSV to RGB with better color accuracy.
  """
  def hsv_to_rgb(h, s, v) do
    c = v * s
    x = c * (1 - abs(rem(trunc(h / 60), 2) - 1))
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
  Get enhanced color with gamma correction.
  """
  def get_enhanced_color(scheme_name, value, brightness) do
    schemes = enhanced_color_schemes()
    scheme = Map.get(schemes, scheme_name)

    if scheme do
      scheme.(value, brightness)
    else
      # Fallback to basic color
      {trunc(255 * brightness * value), trunc(255 * brightness * value), trunc(255 * brightness * value)}
    end
  end

  @doc """
  Adaptive brightness based on overall brightness level.
  """
  def adaptive_brightness(base_brightness, overall_intensity) do
    # Adjust brightness based on overall pattern intensity
    # This prevents patterns from being too bright or too dim
    adjusted = case overall_intensity do
      intensity when intensity < 0.3 -> base_brightness * 1.2  # Boost dim patterns
      intensity when intensity > 0.7 -> base_brightness * 0.8  # Reduce bright patterns
      _ -> base_brightness
    end

    max(0.1, min(1.0, adjusted))
  end

  @doc """
  Calculate overall intensity of a pixel array.
  """
  def calculate_intensity(pixels) do
    total_intensity = Enum.reduce(pixels, 0, fn {r, g, b}, acc ->
      acc + (r + g + b) / 3.0
    end)

    total_intensity / (length(pixels) * 255.0)
  end
end
