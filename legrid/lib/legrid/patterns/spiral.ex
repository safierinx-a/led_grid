defmodule Legrid.Patterns.Spiral do
  @moduledoc """
  Pattern generator for animated spiral patterns.

  Creates dynamic spirals with evolving parameters, radius changes,
  and color transitions.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.{PatternHelpers, SpatialHelpers}

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "spiral",
      name: "Dynamic Spirals",
      description: "Mesmerizing spiral patterns with evolving parameters",
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
        "turns" => %{
          type: :float,
          default: 3.0,
          min: 1.0,
          max: 8.0,
          description: "Number of spiral turns"
        },
        "expansion_rate" => %{
          type: :float,
          default: 0.2,
          min: 0.05,
          max: 0.5,
          description: "Rate of spiral expansion"
        },
        "rotation_speed" => %{
          type: :float,
          default: 0.5,
          min: -2.0,
          max: 2.0,
          description: "Speed of spiral rotation"
        },
        "pulse_amplitude" => %{
          type: :float,
          default: 0.3,
          min: 0.0,
          max: 1.0,
          description: "Amplitude of radius pulsation"
        },
        "pulse_frequency" => %{
          type: :float,
          default: 2.0,
          min: 0.1,
          max: 5.0,
          description: "Frequency of radius pulsation"
        },
        "points" => %{
          type: :integer,
          default: 60,
          min: 10,
          max: 120,
          description: "Number of points to render along spiral"
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
      turns: PatternHelpers.get_param(params, "turns", 3.0, :float),
      expansion_rate: PatternHelpers.get_param(params, "expansion_rate", 0.2, :float),
      rotation_speed: PatternHelpers.get_param(params, "rotation_speed", 0.5, :float),
      pulse_amplitude: PatternHelpers.get_param(params, "pulse_amplitude", 0.3, :float),
      pulse_frequency: PatternHelpers.get_param(params, "pulse_frequency", 2.0, :float),
      points: PatternHelpers.get_param(params, "points", 60, :integer),
      # Animation state
      time: 0.0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time - apply speed multiplier from global parameters
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Create frame
    frame = %Frame{width: state.width, height: state.height, pixels: []}
    center = {state.width / 2.0, state.height / 2.0}

    # Generate spatial fields
    distance_field = SpatialHelpers.distance_field(frame, center)
    angle_field = SpatialHelpers.angle_field(frame, center)

    # Calculate max radius for normalization
    max_radius = SpatialHelpers.max_dimension(frame) / 2.0

    # Create spiral field using spatial operations
    pixels = SpatialHelpers.spatial_to_frame(frame, [distance_field, angle_field],
      fn [distance, angle], _x, _y ->
        # Normalize distance and angle
        norm_distance = distance / max_radius
        norm_angle = (angle + :math.pi) / (2 * :math.pi)  # 0 to 1

        # Calculate spiral parameter
        # Combine angle and distance to create spiral effect
        spiral_t = PatternHelpers.rem_float(
          norm_angle * state.turns +
          norm_distance * state.expansion_rate +
          time * state.rotation_speed,
          1.0
        )

        # Apply pulsation
        pulse = :math.sin(time * state.pulse_frequency + norm_distance * 4 * :math.pi) * state.pulse_amplitude

        # Calculate spiral intensity - creates the "arms" of the spiral
        spiral_intensity = :math.pow(:math.sin(spiral_t * 2 * :math.pi), 2)

        # Apply pulsation to intensity
        final_intensity = spiral_intensity * (1.0 + pulse)

        # Only render if intensity is above threshold
        if final_intensity > 0.1 do
          # Color based on position in spiral
          color_value = PatternHelpers.rem_float(spiral_t + time * 0.1, 1.0)

          # Brightness based on distance (fade toward edges) and intensity
          brightness = final_intensity * (0.4 + norm_distance * 0.6) * state.brightness

          PatternHelpers.get_color(state.color_scheme, color_value, brightness)
        else
          # Background
          {0, 0, 0}
        end
      end)

    # Create the frame
    frame_with_pixels = %{frame | pixels: pixels}

    # Update state
    new_state = %{state | time: time}

    {:ok, frame_with_pixels, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      turns: PatternHelpers.get_param(params, "turns", state.turns, :float),
      expansion_rate: PatternHelpers.get_param(params, "expansion_rate", state.expansion_rate, :float),
      rotation_speed: PatternHelpers.get_param(params, "rotation_speed", state.rotation_speed, :float),
      pulse_amplitude: PatternHelpers.get_param(params, "pulse_amplitude", state.pulse_amplitude, :float),
      pulse_frequency: PatternHelpers.get_param(params, "pulse_frequency", state.pulse_frequency, :float),
      points: PatternHelpers.get_param(params, "points", state.points, :integer)
    }

    {:ok, updated_state}
  end

  # Generate points along a spiral with dynamic parameters
  defp generate_spiral_points(center_x, center_y, max_radius, turns, expansion_rate,
                            pulse_amplitude, pulse_frequency, rotation_speed, point_count, time) do
    # Calculate rotation offset based on time and rotation speed
    rotation = time * rotation_speed

    # Generate points along the spiral
    Enum.map(0..(point_count - 1), fn i ->
      # Normalize position along spiral (0.0 to 1.0)
      t = i / (point_count - 1)

      # Calculate angle based on position and number of turns
      angle = t * turns * 2 * :math.pi + rotation

      # Calculate base radius that grows with t
      base_radius = t * max_radius * expansion_rate

      # Apply pulsation to radius
      pulse = :math.sin(time * pulse_frequency + t * 4 * :math.pi) * pulse_amplitude
      radius = base_radius * (1.0 + pulse)

      # Convert polar coordinates to Cartesian
      x = trunc(center_x + radius * :math.cos(angle))
      y = trunc(center_y + radius * :math.sin(angle))

      # Return point with position and parameter t for coloring
      {x, y, t}
    end)
  end

  # Helper function to render pixels
  defp render_pixels(width, height, points, time, brightness, color_scheme) do
    # Initialize black canvas
    canvas = for _y <- 0..(height - 1), _x <- 0..(width - 1), do: {0, 0, 0}

    # Draw points on canvas
    points
    |> Enum.reduce(canvas, fn {x, y, t}, pixels ->
      # Calculate color value with time offset to animate colors
      color_value = PatternHelpers.rem_float(t + time * 0.1, 1.0)

      # Adjust brightness based on position along spiral
      point_brightness = (0.4 + t * 0.6) * brightness

      # Get color based on scheme and brightness
      {r, g, b} = PatternHelpers.get_color(color_scheme, color_value, point_brightness)

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
