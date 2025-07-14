defmodule Legrid.Patterns.PatternHelpers do
  @moduledoc """
  Helper functions for pattern implementations.

  Provides common utilities for handling global parameters and color transformations
  that can be shared across all pattern implementations.
  """

  @doc """
  Standard color schemes that all patterns can use.
  """
  def color_schemes do
    %{
      "rainbow" => %{
        name: "Rainbow",
        description: "Full spectrum color rotation",
        colors: &rainbow_color/2
      },
      "mono_blue" => %{
        name: "Monochrome Blue",
        description: "Blue color gradient",
        colors: &(mono_color(&1, &2, {0, 0, 255}))
      },
      "mono_red" => %{
        name: "Monochrome Red",
        description: "Red color gradient",
        colors: &(mono_color(&1, &2, {255, 0, 0}))
      },
      "mono_green" => %{
        name: "Monochrome Green",
        description: "Green color gradient",
        colors: &(mono_color(&1, &2, {0, 255, 0}))
      },
      "complementary" => %{
        name: "Complementary",
        description: "Two complementary colors",
        colors: &complementary_color/2
      },
      "cool" => %{
        name: "Cool",
        description: "Cool colors (blues and greens)",
        colors: &cool_color/2
      },
      "warm" => %{
        name: "Warm",
        description: "Warm colors (reds and yellows)",
        colors: &warm_color/2
      },
      # Enhanced color schemes with gamma correction
      "enhanced_rainbow" => %{
        name: "Enhanced Rainbow",
        description: "Improved rainbow with better color transitions",
        colors: &enhanced_rainbow_color/2
      },
      "enhanced_fire" => %{
        name: "Enhanced Fire",
        description: "Enhanced fire effect with better orange/red balance",
        colors: &enhanced_fire_color/2
      },
      "enhanced_ocean" => %{
        name: "Enhanced Ocean",
        description: "Enhanced ocean with better blue/cyan balance",
        colors: &enhanced_ocean_color/2
      },
      "enhanced_sunset" => %{
        name: "Enhanced Sunset",
        description: "Enhanced sunset with better orange/pink balance",
        colors: &enhanced_sunset_color/2
      },
      "enhanced_forest" => %{
        name: "Enhanced Forest",
        description: "Enhanced forest with better green balance",
        colors: &enhanced_forest_color/2
      },
      "enhanced_neon" => %{
        name: "Enhanced Neon",
        description: "Enhanced neon with better saturation",
        colors: &enhanced_neon_color/2
      },
      "enhanced_pastel" => %{
        name: "Enhanced Pastel",
        description: "Enhanced pastel with softer colors",
        colors: &enhanced_pastel_color/2
      },
      "enhanced_monochrome" => %{
        name: "Enhanced Monochrome",
        description: "Enhanced monochrome with better contrast",
        colors: &enhanced_monochrome_color/2
      }
    }
  end

  @doc """
  Get color based on the selected scheme with gamma correction.

  - scheme: Name of the color scheme to use
  - value: Normalized value between 0.0 and 1.0
  - brightness: Brightness multiplier (0.0-1.0)

  Returns RGB tuple {r, g, b} with values 0-255, gamma-corrected for LED displays
  """
  def get_color(scheme, value, brightness \\ 1.0) do
    schemes = color_schemes()

    color_fn = case Map.get(schemes, scheme) do
      %{colors: color_fn} -> color_fn
      _ -> schemes["rainbow"].colors
    end

    # Apply the color function and adjust brightness
    {r, g, b} = color_fn.(value, brightness)

    # Apply gamma correction for better LED display accuracy
    gamma_correct_rgb({r, g, b})
  end

  @doc """
  Apply global parameters to state.

  This standardizes how global parameters are applied to pattern state.
  """
  def apply_global_params(state, params) do
    %{
      state |
      brightness: get_param(params, "brightness", state.brightness || 1.0, :float),
      color_scheme: get_param(params, "color_scheme", state.color_scheme || "rainbow", :string),
      speed: get_param(params, "speed", state.speed || 1.0, :float)
    }
  end

  @doc """
  Standard parameter type conversion with fallback to default.
  """
  def get_param(params, key, default, type) do
    case Map.get(params, key) do
      nil -> default
      value when is_binary(value) and type == :float ->
        case Float.parse(value) do
          {float_val, _} -> float_val
          :error -> default
        end
      value when is_binary(value) and type == :integer ->
        case Integer.parse(value) do
          {int_val, _} -> int_val
          :error -> default
        end
      value when is_number(value) -> value
      value when type == :string -> value
      value when type == :enum -> value
      value when type == :boolean and is_boolean(value) -> value
      "true" when type == :boolean -> true
      "false" when type == :boolean -> false
      _ -> default
    end
  end

  # Color scheme implementations

  defp rainbow_color(value, brightness) do
    # Ensure value is between 0 and 1
    hue = rem_float(value, 1.0)
    hsv_to_rgb(hue, 1.0, brightness)
  end

  defp mono_color(value, brightness, {r, g, b}) do
    # Value impacts brightness in monochrome
    r_out = trunc(r * brightness * value)
    g_out = trunc(g * brightness * value)
    b_out = trunc(b * brightness * value)
    {r_out, g_out, b_out}
  end

  defp complementary_color(value, brightness) do
    # Use two complementary colors (opposite on color wheel)
    if value < 0.5 do
      # First color (e.g., blue)
      hsv_to_rgb(0.6, 1.0, brightness * value * 2)
    else
      # Second color (e.g., orange)
      hsv_to_rgb(0.1, 1.0, brightness * (value - 0.5) * 2)
    end
  end

  defp cool_color(value, brightness) do
    # Cool colors: blues, greens, cyans (hues 0.4-0.7)
    hue = 0.4 + value * 0.3
    hsv_to_rgb(hue, 0.8, brightness)
  end

  defp warm_color(value, brightness) do
    # Warm colors: reds, oranges, yellows (hues 0.0-0.2)
    hue = value * 0.2
    hsv_to_rgb(hue, 0.9, brightness)
  end

  # Enhanced color scheme implementations

  defp enhanced_rainbow_color(value, brightness) do
    # Improved rainbow with better color transitions
    hue = value * 360.0
    rgb = enhanced_hsv_to_rgb(hue, 1.0, brightness)
    rgb
  end

  defp enhanced_fire_color(value, brightness) do
    # Enhanced fire effect with better orange/red balance
    r = min(255, trunc(255 * brightness * (1.0 + value * 0.5)))
    g = min(255, trunc(100 * brightness * value))
    b = min(255, trunc(20 * brightness * value * value))
    {r, g, b}
  end

  defp enhanced_ocean_color(value, brightness) do
    # Enhanced ocean with better blue/cyan balance
    r = min(255, trunc(20 * brightness * value))
    g = min(255, trunc(150 * brightness * (0.3 + value * 0.7)))
    b = min(255, trunc(255 * brightness * (0.5 + value * 0.5)))
    {r, g, b}
  end

  defp enhanced_sunset_color(value, brightness) do
    # Enhanced sunset with better orange/pink balance
    r = min(255, trunc(255 * brightness * (0.7 + value * 0.3)))
    g = min(255, trunc(100 * brightness * value))
    b = min(255, trunc(50 * brightness * value * value))
    {r, g, b}
  end

  defp enhanced_forest_color(value, brightness) do
    # Enhanced forest with better green balance
    r = min(255, trunc(50 * brightness * value))
    g = min(255, trunc(200 * brightness * (0.4 + value * 0.6)))
    b = min(255, trunc(30 * brightness * value))
    {r, g, b}
  end

  defp enhanced_neon_color(value, brightness) do
    # Enhanced neon with better saturation
    hue = value * 360.0
    rgb = enhanced_hsv_to_rgb(hue, 1.0, brightness * 1.2)
    rgb
  end

  defp enhanced_pastel_color(value, brightness) do
    # Enhanced pastel with softer colors
    hue = value * 360.0
    rgb = enhanced_hsv_to_rgb(hue, 0.6, brightness * 0.8)
    rgb
  end

  defp enhanced_monochrome_color(value, brightness) do
    # Enhanced monochrome with better contrast
    intensity = trunc(255 * brightness * value)
    {intensity, intensity, intensity}
  end

  # Helper functions

  # Gamma correction value for LED displays (typically 2.2-2.4)
  @gamma 2.2

  # Apply gamma correction to a color value (0.0 to 1.0)
  defp gamma_correct(value) when is_float(value) and value >= 0.0 and value <= 1.0 do
    :math.pow(value, 1.0 / @gamma)
  end

  defp gamma_correct(value) when is_integer(value) and value >= 0 and value <= 255 do
    normalized = value / 255.0
    corrected = gamma_correct(normalized)
    trunc(corrected * 255)
  end

  # Apply gamma correction to an RGB tuple
  defp gamma_correct_rgb({r, g, b}) do
    {
      gamma_correct(r),
      gamma_correct(g),
      gamma_correct(b)
    }
  end

  # Floating point remainder operation
  def rem_float(a, b) do
    a - b * Float.floor(a / b)
  end

  # Convert HSV color space to RGB
  def hsv_to_rgb(h, s, v) do
    i = trunc(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    {r, g, b} = case rem(i, 6) do
      0 -> {v, t, p}
      1 -> {q, v, p}
      2 -> {p, v, t}
      3 -> {p, q, v}
      4 -> {t, p, v}
      5 -> {v, p, q}
    end

    {trunc(r * 255), trunc(g * 255), trunc(b * 255)}
  end

  # Enhanced HSV to RGB with better color accuracy
  defp enhanced_hsv_to_rgb(h, s, v) do
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
  Applies a function to every value in a field
  """
  def apply_function(field, function) do
    Enum.map(field, function)
  end

  @doc """
  Converts spatial field data back to frame format
  """
  def spatial_to_frame(frame, fields, pixel_function) do
    total_pixels = frame.width * frame.height

    pixels = for i <- 0..(total_pixels - 1) do
      x = rem(i, frame.width)
      y = div(i, frame.width)

      field_values = Enum.map(fields, fn field -> Enum.at(field, i) end)
      pixel_function.(field_values, x, y)
    end

    pixels
  end

  @doc """
  Generates angle field from a center point
  Returns normalized angles in 0-2π range
  """
  def angle_field(frame, {center_x, center_y}) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      angle = :math.atan2(dy, dx)
      # Normalize to 0-2π range
      if angle < 0, do: angle + 2 * :math.pi, else: angle
    end
  end

  @doc """
  Checks if an angle is within a sweep range, handling normalization and wrap-around
  """
  def angle_in_sweep?(angle, sweep_angle, trail_angle) do
    # Normalize all angles to 0-2π range
    norm_angle = normalize_angle(angle)
    norm_sweep = normalize_angle(sweep_angle)
    norm_trail = normalize_angle(trail_angle)

    # Simple range check with wrap-around handling
    if norm_trail <= norm_sweep do
      norm_angle >= norm_trail && norm_angle <= norm_sweep
    else
      norm_angle >= norm_trail || norm_angle <= norm_sweep
    end
  end

  @doc """
  Normalizes an angle to 0-2π range
  """
  def normalize_angle(angle) do
    normalized = Legrid.Patterns.PatternHelpers.rem_float(angle, 2 * :math.pi)
    if normalized < 0, do: normalized + 2 * :math.pi, else: normalized
  end
end

defmodule Legrid.Patterns.SpatialHelpers do
  @moduledoc """
  Spatial operations for LED grid patterns, inspired by Sled concepts.
  """

  @doc """
  Maps colors based on distance from a point
  """
  def map_by_distance(frame, {center_x, center_y}, color_fn) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      distance = :math.sqrt(dx * dx + dy * dy)
      normalized_distance = distance / max_dimension(frame)
      color = color_fn.(normalized_distance)
      {x, y, color}
    end
  end

  @doc """
  Maps colors based on angle from a point
  Automatically normalizes angles to 0-1 range
  """
  def map_by_angle(frame, {center_x, center_y}, color_fn) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      angle = :math.atan2(dy, dx)
      # Normalize to 0-1 range for color functions
      normalized_angle = if angle < 0, do: angle + 2 * :math.pi, else: angle
      normalized_angle = normalized_angle / (2 * :math.pi)
      color = color_fn.(normalized_angle)
      {x, y, color}
    end
  end

  @doc """
  Creates a distance field from a point
  """
  def distance_field(frame, {center_x, center_y}) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      :math.sqrt(dx * dx + dy * dy)
    end
    |> List.flatten()  # Ensure 1D list
  end

  @doc """
  Maps a field of values to colors using a color function
  """
  def map_field_to_colors(field, color_fn) do
    Enum.map(field, fn value ->
      normalized = (value + 1) / 2  # Convert from [-1,1] to [0,1]
      color_fn.(normalized)
    end)
  end

  @doc """
  Blends two distance fields with smooth interpolation
  """
  def smooth_blend(field1, field2, blend_factor) do
    Enum.zip_with(field1, field2, fn d1, d2 ->
      d1 * (1 - blend_factor) + d2 * blend_factor
    end)
  end

  @doc """
  Gets the maximum dimension of a frame
  """
  def max_dimension(frame) do
    max(frame.width, frame.height)
  end

  @doc """
  Creates a circle distance field
  """
  def circle_field(frame, {center_x, center_y}, radius) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      dist = :math.sqrt(dx * dx + dy * dy)
      dist - radius
    end
    |> List.flatten()
  end

  @doc """
  Creates a box distance field
  """
  def box_field(frame, {center_x, center_y}, size) do
    half_size = size / 2
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = abs(x - center_x) - half_size
      dy = abs(y - center_y) - half_size
      cond do
        dx <= 0 and dy <= 0 -> max(dx, dy)
        dx > 0 and dy <= 0 -> dx
        dx <= 0 and dy > 0 -> dy
        true -> :math.sqrt(dx * dx + dy * dy)
      end
    end
    |> List.flatten()
  end

  @doc """
  Creates a line distance field
  """
  def line_field(frame, {x1, y1}, {x2, y2}) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      # Line segment distance formula
      px = x2 - x1
      py = y2 - y1
      norm = px * px + py * py
      u = if norm == 0, do: 0, else: ((x - x1) * px + (y - y1) * py) / norm
      u = max(0, min(1, u))
      dx = x1 + u * px - x
      dy = y1 + u * py - y
      :math.sqrt(dx * dx + dy * dy)
    end
    |> List.flatten()
  end

  @doc """
  Combines multiple fields using a reduction function
  """
  def combine_fields(fields, combine_fn) do
    case fields do
      [] -> []
      [first | rest] -> Enum.reduce(rest, first, combine_fn)
    end
  end

  @doc """
  Converts a list of {x, y, color} tuples to a flat list of colors in frame order
  """
  def to_frame_pixels(coords, width, height) do
    # Create array of default black pixels
    pixels = List.duplicate({0, 0, 0}, width * height)

    # Update with actual colors
    Enum.reduce(coords, pixels, fn {x, y, color}, acc ->
      if x >= 0 and x < width and y >= 0 and y < height do
        List.replace_at(acc, y * width + x, color)
      else
        acc
      end
    end)
  end

  @doc """
  Applies a wave function to a distance field
  """
  def apply_wave(field, frequency, phase, amplitude \\ 1.0) do
    Enum.map(field, fn dist ->
      :math.sin(dist * frequency + phase) * amplitude
    end)
  end

  @doc """
  Common field combination modes
  """
  def combine_additive(field1, field2), do: Enum.zip_with(field1, field2, &((&1 + &2) / 2))
  def combine_multiplicative(field1, field2), do: Enum.zip_with(field1, field2, &(&1 * &2))
  def combine_maximum(field1, field2), do: Enum.zip_with(field1, field2, &max(&1, &2))

  @doc """
  Applies a function to every value in a field
  """
  def apply_function(field, function) do
    Enum.map(field, function)
  end

  @doc """
  Converts spatial field data back to frame format
  """
  def spatial_to_frame(frame, fields, pixel_function) do
    total_pixels = frame.width * frame.height

    pixels = for i <- 0..(total_pixels - 1) do
      x = rem(i, frame.width)
      y = div(i, frame.width)

      field_values = Enum.map(fields, fn field -> Enum.at(field, i) end)
      pixel_function.(field_values, x, y)
    end

    pixels
  end

  @doc """
  Generates angle field from a center point
  Returns normalized angles in 0-2π range
  """
  def angle_field(frame, {center_x, center_y}) do
    for y <- 0..frame.height-1,
        x <- 0..frame.width-1 do
      dx = x - center_x
      dy = y - center_y
      angle = :math.atan2(dy, dx)
      # Normalize to 0-2π range
      if angle < 0, do: angle + 2 * :math.pi, else: angle
    end
  end

  @doc """
  Checks if an angle is within a sweep range, handling normalization and wrap-around
  """
  def angle_in_sweep?(angle, sweep_angle, trail_angle) do
    # Normalize all angles to 0-2π range
    norm_angle = normalize_angle(angle)
    norm_sweep = normalize_angle(sweep_angle)
    norm_trail = normalize_angle(trail_angle)

    # Simple range check with wrap-around handling
    if norm_trail <= norm_sweep do
      norm_angle >= norm_trail && norm_angle <= norm_sweep
    else
      norm_angle >= norm_trail || norm_angle <= norm_sweep
    end
  end

  @doc """
  Normalizes an angle to 0-2π range
  """
  def normalize_angle(angle) do
    normalized = Legrid.Patterns.PatternHelpers.rem_float(angle, 2 * :math.pi)
    if normalized < 0, do: normalized + 2 * :math.pi, else: normalized
  end
end
