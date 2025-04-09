defmodule Legrid.Patterns.Lissajous do
  @moduledoc """
  Pattern generator for Lissajous figures.

  Creates moving Lissajous curves with dynamically shifting parameters.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    %{
      id: "lissajous",
      name: "Lissajous Figures",
      description: "Hypnotic Lissajous curves with shifting parameters",
      parameters: %{
        "a_freq" => %{
          type: :float,
          default: 3.0,
          min: 1.0,
          max: 10.0,
          description: "X frequency multiplier"
        },
        "b_freq" => %{
          type: :float,
          default: 2.0,
          min: 1.0,
          max: 10.0,
          description: "Y frequency multiplier"
        },
        "phase_shift" => %{
          type: :float,
          default: 0.5,
          min: 0.0,
          max: 3.14,
          description: "Phase difference between X and Y"
        },
        "morph_speed" => %{
          type: :float,
          default: 0.1,
          min: 0.0,
          max: 1.0,
          description: "Speed of parameter evolution"
        },
        "tail_length" => %{
          type: :integer,
          default: 30,
          min: 1,
          max: 100,
          description: "Length of the Lissajous curve trail"
        },
        "brightness" => %{
          type: :float,
          default: 0.8,
          min: 0.1,
          max: 1.0,
          description: "Brightness of the curve"
        }
      }
    }
  end

  @impl true
  def init(params) do
    state = %{
      width: @default_width,
      height: @default_height,
      a_freq: get_param(params, "a_freq", 3.0, :float),
      b_freq: get_param(params, "b_freq", 2.0, :float),
      phase_shift: get_param(params, "phase_shift", 0.5, :float),
      morph_speed: get_param(params, "morph_speed", 0.1, :float),
      tail_length: get_param(params, "tail_length", 30, :integer),
      brightness: get_param(params, "brightness", 0.8, :float),
      time: 0.0,
      trail: []
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time
    delta_time = elapsed_ms / 1000.0
    time = state.time + delta_time

    # Calculate slowly evolving parameters
    a_freq = state.a_freq + :math.sin(time * 0.2 * state.morph_speed) * 0.1
    b_freq = state.b_freq + :math.cos(time * 0.15 * state.morph_speed) * 0.1
    phase_shift = state.phase_shift + :math.sin(time * 0.1 * state.morph_speed) * 0.05

    # Calculate current position
    x = :math.sin(a_freq * time)
    y = :math.sin(b_freq * time + phase_shift)

    # Scale to grid coordinates
    grid_x = trunc((x + 1.0) * (state.width - 1) / 2)
    grid_y = trunc((y + 1.0) * (state.height - 1) / 2)

    # Update trail
    trail = [{grid_x, grid_y, time} | state.trail]
    |> Enum.take(state.tail_length)

    # Generate pixels for the frame
    pixels = render_pixels(state.width, state.height, trail, time, state.brightness)

    # Create the frame
    frame = Frame.new("lissajous", state.width, state.height, pixels)

    # Update state
    new_state = %{state |
      time: time,
      trail: trail,
      a_freq: a_freq,
      b_freq: b_freq,
      phase_shift: phase_shift
    }

    {:ok, frame, new_state}
  end

  # Helper function to render pixels
  defp render_pixels(width, height, trail, time, max_brightness) do
    # Initialize black canvas
    canvas = for _y <- 0..(height - 1), _x <- 0..(width - 1), do: {0, 0, 0}

    # Draw trail on canvas
    trail
    |> Enum.with_index()
    |> Enum.reduce(canvas, fn {{x, y, point_time}, idx}, pixels ->
      # Calculate brightness based on age
      age_factor = 1.0 - (idx / length(trail))
      brightness = age_factor * max_brightness

      # Calculate color based on time and position
      hue = (time * 0.1 + idx / length(trail)) |> rem_float(1.0)
      {r, g, b} = hsv_to_rgb(hue, 1.0, brightness)

      # Update pixel if in bounds
      if x >= 0 and x < width and y >= 0 and y < height do
        index = y * width + x
        List.replace_at(pixels, index, {r, g, b})
      else
        pixels
      end
    end)
  end

  # Floating point remainder operation
  defp rem_float(a, b) do
    a - b * Float.floor(a / b)
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
