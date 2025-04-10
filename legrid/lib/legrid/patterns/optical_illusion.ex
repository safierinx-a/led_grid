defmodule Legrid.Patterns.OpticalIllusion do
  @moduledoc """
  Pattern generator for optical illusions.

  Creates visual illusions that simulate movement or depth using static elements
  with various animation options and parameters.
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
      id: "optical_illusion",
      name: "Optical Illusion",
      description: "Visual illusions that create movement and depth effects",
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
        "illusion_type" => %{
          type: :enum,
          default: "pulsing_grid",
          options: ["pulsing_grid", "rotating_rings", "moving_waves", "expanding_circles", "spiral"],
          description: "Type of optical illusion"
        },
        "phase_shift" => %{
          type: :float,
          default: 0.2,
          min: 0.0,
          max: 1.0,
          description: "Phase shift between elements"
        },
        "density" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 1.0,
          description: "Density of elements in the pattern"
        },
        "contrast" => %{
          type: :float,
          default: 0.8,
          min: 0.1,
          max: 1.0,
          description: "Contrast between elements"
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
      illusion_type: PatternHelpers.get_param(params, "illusion_type", "pulsing_grid", :string),
      phase_shift: PatternHelpers.get_param(params, "phase_shift", 0.2, :float),
      density: PatternHelpers.get_param(params, "density", 0.5, :float),
      contrast: PatternHelpers.get_param(params, "contrast", 0.8, :float),
      # Animation state
      time: 0.0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds with speed factor
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Generate pixels based on illusion type
    pixels = case state.illusion_type do
      "pulsing_grid" -> render_pulsing_grid(state.width, state.height, time, state)
      "rotating_rings" -> render_rotating_rings(state.width, state.height, time, state)
      "moving_waves" -> render_moving_waves(state.width, state.height, time, state)
      "expanding_circles" -> render_expanding_circles(state.width, state.height, time, state)
      "spiral" -> render_spiral(state.width, state.height, time, state)
      _ -> render_pulsing_grid(state.width, state.height, time, state)
    end

    # Create the frame
    frame = Frame.new("optical_illusion", state.width, state.height, pixels)

    # Update state with new time
    new_state = %{state | time: time}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      illusion_type: PatternHelpers.get_param(params, "illusion_type", state.illusion_type, :string),
      phase_shift: PatternHelpers.get_param(params, "phase_shift", state.phase_shift, :float),
      density: PatternHelpers.get_param(params, "density", state.density, :float),
      contrast: PatternHelpers.get_param(params, "contrast", state.contrast, :float)
    }

    {:ok, updated_state}
  end

  # Helper functions for rendering different illusion types

  # Pulsing Grid: Creates a grid with cells that pulse at different rates
  defp render_pulsing_grid(width, height, time, state) do
    # Calculate grid cell size based on density
    cell_size = max(1, trunc(1.0 / state.density) + 1)

    for y <- 0..(height-1), x <- 0..(width-1) do
      # Determine which grid cell this pixel belongs to
      grid_x = div(x, cell_size)
      grid_y = div(y, cell_size)

      # Calculate pulse for this cell (offset by position for varied effect)
      pulse_rate = 2.0 * :math.pi * (1.0 + grid_x * grid_y * state.phase_shift * 0.1)
      pulse = (:math.sin(time * pulse_rate + grid_x * grid_y * state.phase_shift) + 1.0) / 2.0

      # Calculate intensity based on position within cell
      cell_center_x = (grid_x * cell_size) + div(cell_size, 2)
      cell_center_y = (grid_y * cell_size) + div(cell_size, 2)
      dist_from_center = :math.sqrt(:math.pow(x - cell_center_x, 2) + :math.pow(y - cell_center_y, 2))

      # Apply contrast to make the effect stronger
      intensity = pulse * max(0, 1.0 - (dist_from_center / (cell_size / 2.0))) * state.contrast

      # Apply color based on position and time
      color_value = PatternHelpers.rem_float(grid_x * 0.05 + grid_y * 0.07 + time * 0.1, 1.0)
      PatternHelpers.get_color(state.color_scheme, color_value, intensity * state.brightness)
    end
  end

  # Rotating Rings: Concentric rings that appear to rotate
  defp render_rotating_rings(width, height, time, state) do
    center_x = width / 2.0
    center_y = height / 2.0
    max_radius = :math.sqrt(center_x * center_x + center_y * center_y)

    for y <- 0..(height-1), x <- 0..(width-1) do
      # Calculate polar coordinates
      dx = x - center_x
      dy = y - center_y
      radius = :math.sqrt(dx * dx + dy * dy)
      angle = :math.atan2(dy, dx)

      # Number of rings based on density
      ring_count = trunc(max_radius * state.density * 1.5) + 3
      ring_thickness = max_radius / ring_count

      # Calculate ring value with rotation
      ring_value = rem_float(radius / ring_thickness +
                           angle / (2.0 * :math.pi) +
                           time * 0.5, 1.0)

      # Apply contrast - rings have sharp transitions
      ring_pulse = if ring_value > 0.5, do: 1.0, else: 0.0

      # Apply additional rotation based on radius
      color_angle = angle + radius * state.phase_shift * :math.sin(time)
      color_value = PatternHelpers.rem_float(color_angle / (2.0 * :math.pi) + time * 0.2, 1.0)

      # Mix dark and light colors based on ring value
      final_brightness = ring_pulse * state.contrast * state.brightness
      PatternHelpers.get_color(state.color_scheme, color_value, final_brightness)
    end
  end

  # Moving Waves: Creates wave patterns that appear to move across the grid
  defp render_moving_waves(width, height, time, state) do
    wave_frequency = 5.0 + state.density * 15.0  # Higher density = more waves

    for y <- 0..(height-1), x <- 0..(width-1) do
      # Create multiple overlapping waves
      norm_x = x / width
      norm_y = y / height

      # First wave: horizontal
      wave1 = :math.sin(norm_y * wave_frequency * 2.0 * :math.pi + time * 3.0)

      # Second wave: vertical
      wave2 = :math.sin(norm_x * wave_frequency * 2.0 * :math.pi - time * 2.0)

      # Third wave: diagonal
      wave3 = :math.sin((norm_x + norm_y) * wave_frequency * :math.pi + time * 4.0)

      # Combine waves with phase shifts
      combined = (wave1 + wave2 + wave3) / 3.0
      intensity = (combined + 1.0) / 2.0

      # Apply contrast
      intensity = :math.pow(intensity, 1.0 / state.contrast)

      # Color based on position and time
      color_value = PatternHelpers.rem_float(norm_x + norm_y + time * 0.1, 1.0)
      PatternHelpers.get_color(state.color_scheme, color_value, intensity * state.brightness)
    end
  end

  # Expanding Circles: Circles that expand outward from the center
  defp render_expanding_circles(width, height, time, state) do
    center_x = width / 2.0
    center_y = height / 2.0
    max_radius = :math.sqrt(center_x * center_x + center_y * center_y)

    # Calculate how many circles to display based on density
    circle_count = trunc(state.density * 10.0) + 2

    for y <- 0..(height-1), x <- 0..(width-1) do
      # Calculate distance from center
      dx = x - center_x
      dy = y - center_y
      radius = :math.sqrt(dx * dx + dy * dy)

      # Normalize radius and create expanding effect
      norm_radius = radius / max_radius
      expanding_value = rem_float(norm_radius * circle_count - time, 1.0)

      # Create sharp transitions between circles
      circle_edge = if abs(expanding_value - 0.5) < state.contrast * 0.3, do: 1.0, else: 0.0

      # Add some variation based on angle
      angle = :math.atan2(dy, dx)
      color_value = PatternHelpers.rem_float(angle / (2.0 * :math.pi) + time * 0.1, 1.0)

      PatternHelpers.get_color(state.color_scheme, color_value, circle_edge * state.brightness)
    end
  end

  # Spiral: Creates a spinning spiral pattern
  defp render_spiral(width, height, time, state) do
    center_x = width / 2.0
    center_y = height / 2.0
    max_radius = :math.sqrt(center_x * center_x + center_y * center_y)

    # Number of spiral arms based on density
    arm_count = trunc(state.density * 10.0) + 1

    for y <- 0..(height-1), x <- 0..(width-1) do
      # Calculate polar coordinates
      dx = x - center_x
      dy = y - center_y
      radius = :math.sqrt(dx * dx + dy * dy)
      angle = :math.atan2(dy, dx)

      # Create spiral effect by combining angle and radius
      spiral_value = rem_float((angle / (2.0 * :math.pi) * arm_count +
                             radius / max_radius + time), 1.0)

      # Apply contrast to create defined spiral arms
      spiral_intensity = :math.pow(spiral_value, state.contrast * 3.0)

      # Color based on radius and time
      color_value = PatternHelpers.rem_float(radius / max_radius + time * 0.2, 1.0)

      # Apply pulsing brightness based on time
      pulse = (1.0 + :math.sin(time * 2.0)) / 2.0

      # Combine effects
      final_brightness = spiral_intensity * state.brightness * (0.5 + pulse * 0.5)
      PatternHelpers.get_color(state.color_scheme, color_value, final_brightness)
    end
  end

  # Helper for floating point remainder that handles negative values correctly
  defp rem_float(a, b) do
    PatternHelpers.rem_float(a, b)
  end
end
