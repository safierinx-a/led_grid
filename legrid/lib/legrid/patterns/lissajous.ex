defmodule Legrid.Patterns.Lissajous do
  @moduledoc """
  Pattern generator for Lissajous figures.

  Creates moving Lissajous curves with dynamically shifting parameters.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "lissajous",
      name: "Lissajous Figures",
      description: "Hypnotic Lissajous curves with shifting parameters",
      parameters: %{
        # Global parameters
        "brightness" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 1.0,
          description: "Overall brightness"
        },
        "color_scheme" => %{
          type: :enum,
          default: "rainbow",
          options: color_scheme_options,
          description: "Color scheme to use"
        },
        "speed" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 2.0,
          description: "Animation speed"
        },
        # Pattern-specific parameters
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
        }
      }
    }
  end

  @impl true
  def init(params) do
    state = %{
      width: @default_width,
      height: @default_height,
      # Global parameters
      brightness: PatternHelpers.get_param(params, "brightness", 1.0, :float),
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "rainbow", :string),
      speed: PatternHelpers.get_param(params, "speed", 1.0, :float),
      # Pattern-specific parameters
      a_freq: PatternHelpers.get_param(params, "a_freq", 3.0, :float),
      b_freq: PatternHelpers.get_param(params, "b_freq", 2.0, :float),
      phase_shift: PatternHelpers.get_param(params, "phase_shift", 0.5, :float),
      morph_speed: PatternHelpers.get_param(params, "morph_speed", 0.1, :float),
      tail_length: PatternHelpers.get_param(params, "tail_length", 30, :integer),
      # Animation state
      time: 0.0,
      trail: []
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time - apply speed multiplier from global parameters
    delta_time = elapsed_ms / 1000.0 * state.speed
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
    pixels = render_pixels(state.width, state.height, trail, time, state.brightness, state.color_scheme)

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

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      a_freq: PatternHelpers.get_param(params, "a_freq", state.a_freq, :float),
      b_freq: PatternHelpers.get_param(params, "b_freq", state.b_freq, :float),
      phase_shift: PatternHelpers.get_param(params, "phase_shift", state.phase_shift, :float),
      morph_speed: PatternHelpers.get_param(params, "morph_speed", state.morph_speed, :float),
      tail_length: PatternHelpers.get_param(params, "tail_length", state.tail_length, :integer)
    }

    {:ok, updated_state}
  end

  # Helper function to render pixels
  defp render_pixels(width, height, trail, time, brightness, color_scheme) do
    # Initialize black canvas
    canvas = for _y <- 0..(height - 1), _x <- 0..(width - 1), do: {0, 0, 0}

    # Draw trail on canvas
    trail
    |> Enum.with_index()
    |> Enum.reduce(canvas, fn {{x, y, point_time}, idx}, pixels ->
      # Calculate brightness based on age
      age_factor = 1.0 - (idx / length(trail))
      pixel_brightness = age_factor * brightness

      # Calculate color value (normalized for color selection)
      color_value = PatternHelpers.rem_float(time * 0.1 + idx / length(trail), 1.0)

      # Get color based on scheme and brightness
      {r, g, b} = PatternHelpers.get_color(color_scheme, color_value, pixel_brightness)

      # Update pixel if in bounds
      if x >= 0 and x < width and y >= 0 and y < height do
        index = y * width + x
        List.replace_at(pixels, index, {r, g, b})
      else
        pixels
      end
    end)
  end
end
