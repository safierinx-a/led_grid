defmodule Legrid.Patterns.SineWave do
  @moduledoc """
  Pattern generator for sine wave animations.

  Creates colorful sine waves that move across the grid.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    %{
      id: "sine_wave",
      name: "Sine Wave",
      description: "Colorful sine waves that move across the grid",
      parameters: %{
        "amplitude" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 1.0,
          description: "Height of the wave"
        },
        "frequency" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 5.0,
          description: "Number of waves across the grid"
        },
        "speed" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 2.0,
          description: "Speed of wave movement"
        },
        "color_speed" => %{
          type: :float,
          default: 0.2,
          min: 0.0,
          max: 1.0,
          description: "Speed of color cycling"
        }
      }
    }
  end

  @impl true
  def init(params) do
    state = %{
      width: @default_width,
      height: @default_height,
      amplitude: get_param(params, "amplitude", 0.5, :float),
      frequency: get_param(params, "frequency", 1.0, :float),
      speed: get_param(params, "speed", 0.5, :float),
      color_speed: get_param(params, "color_speed", 0.2, :float),
      phase: 0.0,
      color_phase: 0.0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update phases
    delta_time = elapsed_ms / 1000.0
    phase = state.phase + (state.speed * delta_time)
    color_phase = state.color_phase + (state.color_speed * delta_time)

    # Generate pixels for the frame
    pixels = generate_sine_wave(state.width, state.height,
                               state.amplitude, state.frequency,
                               phase, color_phase)

    # Create the frame
    frame = Frame.new("sine_wave", state.width, state.height, pixels)

    # Update state with new phases
    new_state = %{state | phase: phase, color_phase: color_phase}

    {:ok, frame, new_state}
  end

  # Helper function to generate sine wave pattern
  defp generate_sine_wave(width, height, amplitude, frequency, phase, color_phase) do
    for y <- 0..(height - 1), x <- 0..(width - 1) do
      # Calculate wave value at this x position
      wave_val = amplitude * :math.sin(2 * :math.pi * frequency * (x / width) + phase)

      # Map to y position
      wave_y = trunc((height / 2) + (wave_val * height / 2))

      # Distance from wave
      dist = abs(y - wave_y)

      # Calculate brightness based on distance from wave
      brightness = if dist < 3, do: 1.0 - (dist / 3), else: 0.0

      # Calculate color (rotate through hue over time)
      hue = rem(trunc(color_phase * 360 + x * 360 / width), 360) / 360.0
      {r, g, b} = hsv_to_rgb(hue, 1.0, brightness)

      {r, g, b}
    end
  end

  # Convert HSV color space to RGB
  defp hsv_to_rgb(h, s, v) do
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

  # Helper to convert parameters to the right type
  defp get_param(params, key, default, type) do
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
      _ -> default
    end
  end
end
