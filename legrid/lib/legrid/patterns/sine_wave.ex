defmodule Legrid.Patterns.SineField do
  @moduledoc """
  Pattern generator for sine field animations.

  Creates colorful sine fields that move across the grid.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    %{
      id: "sine_field",
      name: "Sine Field",
      description: "Enhanced sine fields with gamma-corrected colors",
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
          default: "enhanced_rainbow",
          options: ["enhanced_rainbow", "enhanced_fire", "enhanced_ocean", "enhanced_sunset",
                   "enhanced_neon", "enhanced_forest", "enhanced_pastel", "enhanced_monochrome"],
          description: "Enhanced color scheme with gamma correction"
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
      # Animation state
      time: 0.0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds with speed factor
    delta_time = elapsed_ms / 1000.0
    time = state.time + delta_time

    # Generate pixels using enhanced color schemes
    pixels = for y <- 0..(state.height-1), x <- 0..(state.width-1) do
      # Calculate wave value
      wave_x = x / state.width * 2 * :math.pi * state.frequency
      wave_y = y / state.height * 2 * :math.pi * state.frequency

      # Combine waves with time animation
      wave_value = :math.sin(wave_x + time * state.speed) * state.amplitude +
                   :math.sin(wave_y + time * state.speed * 0.7) * state.amplitude * 0.5

      # Normalize to 0-1 range
      normalized_value = (wave_value + 1) / 2

      # Apply color scheme with gamma correction
      PatternHelpers.get_color(
        state.color_scheme,
        normalized_value,
        state.brightness
      )
    end

    # Create the frame
    frame = Frame.new("sine_field", state.width, state.height, pixels)

    # Update state with new time
    new_state = %{state | time: time}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      amplitude: PatternHelpers.get_param(params, "amplitude", state.amplitude, :float),
      frequency: PatternHelpers.get_param(params, "frequency", state.frequency, :float)
    }

    {:ok, updated_state}
  end


end
