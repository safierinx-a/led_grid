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
end
