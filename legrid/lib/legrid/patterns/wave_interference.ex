defmodule Legrid.Patterns.WaveInterference do
  @moduledoc """
  Pattern generator for wave interference patterns.

  Creates dynamic patterns based on multiple wave sources interacting with each other.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers
  alias Legrid.Patterns.SpatialHelpers

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "wave_interference",
      name: "Wave Interference",
      description: "Dynamic patterns from interacting wave sources",
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
        "wave_count" => %{
          type: :integer,
          default: 3,
          min: 1,
          max: 5,
          description: "Number of wave sources"
        },
        "frequency" => %{
          type: :float,
          default: 0.2,
          min: 0.05,
          max: 0.5,
          description: "Base wave frequency"
        },
        "amplitude" => %{
          type: :float,
          default: 1.0,
          min: 0.5,
          max: 2.0,
          description: "Wave amplitude"
        },
        "wave_speed" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 3.0,
          description: "Wave propagation speed"
        },
        "source_movement" => %{
          type: :float,
          default: 0.5,
          min: 0.0,
          max: 1.0,
          description: "Wave source movement speed"
        },
        "interference_mode" => %{
          type: :enum,
          default: "additive",
          options: ["additive", "multiplicative", "maximum"],
          description: "How waves interact with each other"
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
      wave_count: PatternHelpers.get_param(params, "wave_count", 3, :integer),
      frequency: PatternHelpers.get_param(params, "frequency", 0.2, :float),
      amplitude: PatternHelpers.get_param(params, "amplitude", 1.0, :float),
      wave_speed: PatternHelpers.get_param(params, "wave_speed", 1.0, :float),
      source_movement: PatternHelpers.get_param(params, "source_movement", 0.5, :float),
      interference_mode: PatternHelpers.get_param(params, "interference_mode", "additive", :string),
      # Animation state
      time: 0.0,
      # Initialize wave sources with random positions
      wave_sources: init_wave_sources(@default_width, @default_height,
                    PatternHelpers.get_param(params, "wave_count", 3, :integer))
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Create empty frame
    frame = %Frame{
      width: state.width,
      height: state.height,
      pixels: []
    }

    time = elapsed_ms / 1000

    # Update wave source positions
    wave_sources = update_wave_sources(
      state.wave_sources,
      state.width,
      state.height,
      time,
      state.source_movement
    )

    # Generate distance fields for each source
    fields = Enum.map(wave_sources, fn source ->
      SpatialHelpers.distance_field(frame, {source.x, source.y})
    end)

    # Apply wave function to each field
    wave_fields = Enum.map(fields, fn field ->
      SpatialHelpers.apply_wave(
        field,
        state.frequency,
        time * state.wave_speed,
        state.amplitude
      )
    end)

    # Combine fields based on interference mode
    combine_fn = case state.interference_mode do
      "additive" -> &SpatialHelpers.combine_additive/2
      "multiplicative" -> &SpatialHelpers.combine_multiplicative/2
      "maximum" -> &SpatialHelpers.combine_maximum/2
    end

    combined_field = SpatialHelpers.combine_fields(wave_fields, combine_fn)

    # Map field to colors and convert to frame format
    pixels = combined_field
    |> Enum.with_index()
    |> Enum.map(fn {value, i} ->
      x = rem(i, state.width)
      y = div(i, state.width)
      # Get color and apply wave intensity to brightness
      intensity = (abs(value) + 1) / 2
      PatternHelpers.get_color(state.color_scheme, intensity, state.brightness)
    end)

    # Return frame with updated pixels and state
    {:ok, %{frame | pixels: pixels}, %{state | wave_sources: wave_sources}}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Get new wave count
    new_wave_count = PatternHelpers.get_param(params, "wave_count", state.wave_count, :integer)

    # Reinitialize wave sources if count changes
    wave_sources = if new_wave_count != state.wave_count do
      init_wave_sources(state.width, state.height, new_wave_count)
    else
      state.wave_sources
    end

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      wave_count: new_wave_count,
      frequency: PatternHelpers.get_param(params, "frequency", state.frequency, :float),
      amplitude: PatternHelpers.get_param(params, "amplitude", state.amplitude, :float),
      wave_speed: PatternHelpers.get_param(params, "wave_speed", state.wave_speed, :float),
      source_movement: PatternHelpers.get_param(params, "source_movement", state.source_movement, :float),
      interference_mode: PatternHelpers.get_param(params, "interference_mode", state.interference_mode, :string),
      wave_sources: wave_sources
    }

    {:ok, updated_state}
  end

  # Initialize wave sources with random positions and directions
  defp init_wave_sources(width, height, count) do
    Enum.map(1..count, fn _ ->
      # Random position within grid bounds
      x = :rand.uniform(width - 1)
      y = :rand.uniform(height - 1)

      # Random movement direction (angle in radians)
      angle = :rand.uniform() * 2 * :math.pi

      # Random frequency offset
      freq_offset = :rand.uniform() * 0.2

      %{
        x: x,
        y: y,
        angle: angle,
        freq_offset: freq_offset
      }
    end)
  end

  # Update wave source positions
  defp update_wave_sources(sources, width, height, time, movement_speed) do
    sources
    |> Enum.map(fn source ->
      # Calculate new position based on movement direction and speed
      new_x = source.x + :math.cos(source.angle) * movement_speed * 0.1
      new_y = source.y + :math.sin(source.angle) * movement_speed * 0.1

      # Check boundaries and bounce if needed
      {new_x, _} = bounce_coordinate(new_x, source.angle, 0, width - 1)
      {new_y, new_angle_y} = bounce_coordinate(new_y, source.angle, 0, height - 1)

      # Apply slight direction change over time for more organic movement
      angle_drift = :math.sin(time * 0.2 + source.freq_offset * 10) * 0.03

      %{
        x: new_x,
        y: new_y,
        angle: new_angle_y + angle_drift,  # Use bounced angle and add drift
        freq_offset: source.freq_offset
      }
    end)
  end

  # Helper to handle boundary bouncing
  defp bounce_coordinate(pos, angle, min, max) do
    cond do
      pos < min ->
        {min, reflect_angle(angle)}
      pos > max ->
        {max, reflect_angle(angle)}
      true ->
        {pos, angle}
    end
  end

  # Helper to reflect an angle (for bouncing)
  defp reflect_angle(angle) do
    # Simple reflection by adding π (180 degrees)
    PatternHelpers.rem_float(angle + :math.pi, 2 * :math.pi)
  end

  # Calculate wave amplitude at a point from a source
  defp calculate_wave(x, y, source, time, frequency, amplitude, wave_speed) do
    # Calculate distance from source to point
    dx = x - source.x
    dy = y - source.y
    distance = :math.sqrt(dx * dx + dy * dy)

    # Calculate wave value based on distance and time
    # Adding frequency offset to make each source unique
    wave_val = :math.sin(distance * frequency +
               time * wave_speed + source.freq_offset * :math.pi * 2) * amplitude

    # Apply distance falloff
    attenuation = 1.0 / (1.0 + distance * 0.1)
    wave_val * attenuation
  end

  # Normalize wave value to range [-1, 1]
  defp normalize_wave(value) do
    max_val = max(abs(value), 1.0)
    value / max_val
  end
end
