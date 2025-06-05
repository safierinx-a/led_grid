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
      }
    }
  end

  @doc """
  Get color based on the selected scheme.

  - scheme: Name of the color scheme to use
  - value: Normalized value between 0.0 and 1.0
  - brightness: Brightness multiplier (0.0-1.0)

  Returns RGB tuple {r, g, b} with values 0-255
  """
  def get_color(scheme, value, brightness \\ 1.0) do
    schemes = color_schemes()

    color_fn = case Map.get(schemes, scheme) do
      %{colors: color_fn} -> color_fn
      _ -> schemes["rainbow"].colors
    end

    # Apply the color function and adjust brightness
    {r, g, b} = color_fn.(value, brightness)

    {r, g, b}
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

  # Helper functions

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
