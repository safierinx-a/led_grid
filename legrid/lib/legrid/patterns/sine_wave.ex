defmodule Legrid.Patterns.SineWave do
  @moduledoc """
  Pattern generator for sine wave animations.

  Creates colorful sine waves that move across the grid.
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
      id: "sine_wave",
      name: "Sine Wave",
      description: "Colorful sine waves that move across the grid",
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
          default: 0.5,
          min: 0.1,
          max: 2.0,
          description: "Animation speed"
        },
        # Pattern-specific parameters
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
      # Global parameters
      brightness: PatternHelpers.get_param(params, "brightness", 1.0, :float),
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "rainbow", :string),
      speed: PatternHelpers.get_param(params, "speed", 0.5, :float),
      # Pattern-specific parameters
      amplitude: PatternHelpers.get_param(params, "amplitude", 0.5, :float),
      frequency: PatternHelpers.get_param(params, "frequency", 1.0, :float),
      color_speed: PatternHelpers.get_param(params, "color_speed", 0.2, :float),
      # Animation state
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
                               phase, color_phase, state.color_scheme, state.brightness)

    # Create the frame
    frame = Frame.new("sine_wave", state.width, state.height, pixels)

    # Update state with new phases
    new_state = %{state | phase: phase, color_phase: color_phase}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      amplitude: PatternHelpers.get_param(params, "amplitude", state.amplitude, :float),
      frequency: PatternHelpers.get_param(params, "frequency", state.frequency, :float),
      color_speed: PatternHelpers.get_param(params, "color_speed", state.color_speed, :float)
    }

    {:ok, updated_state}
  end

  # Helper function to generate sine wave pattern
  defp generate_sine_wave(width, height, amplitude, frequency, phase, color_phase, color_scheme, brightness) do
    for y <- 0..(height - 1), x <- 0..(width - 1) do
      # Calculate wave value at this x position
      wave_val = amplitude * :math.sin(2 * :math.pi * frequency * (x / width) + phase)

      # Map to y position
      wave_y = trunc((height / 2) + (wave_val * height / 2))

      # Distance from wave
      dist = abs(y - wave_y)

      # Calculate brightness based on distance from wave
      pixel_brightness = if dist < 3, do: 1.0 - (dist / 3), else: 0.0

      # Apply global brightness
      pixel_brightness = pixel_brightness * brightness

      # Calculate color value (normalized position for color selection)
      color_value = PatternHelpers.rem_float(color_phase + x / width, 1.0)

      # Get color based on scheme
      PatternHelpers.get_color(color_scheme, color_value, pixel_brightness)
    end
  end
end
