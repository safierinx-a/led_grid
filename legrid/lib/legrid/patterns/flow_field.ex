defmodule Legrid.Patterns.FlowField do
  @moduledoc """
  Pattern generator for flow field visualizations.

  Creates dynamic particle systems that follow vector fields
  defined by mathematical functions.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  # Define field types with descriptions
  @field_types %{
    "perlin" => "Perlin noise based flow",
    "circular" => "Circular/vortex flow",
    "sine_wave" => "Sine wave based flow",
    "attractor" => "Strange attractor inspired flow"
  }

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "flow_field",
      name: "Flow Fields",
      description: "Particles flowing through dynamic vector fields",
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
        "field_type" => %{
          type: :enum,
          default: "perlin",
          options: Map.keys(@field_types),
          description: "Type of vector field"
        },
        "particle_count" => %{
          type: :integer,
          default: 40,
          min: 10,
          max: 100,
          description: "Number of particles"
        },
        "field_scale" => %{
          type: :float,
          default: 0.1,
          min: 0.01,
          max: 0.3,
          description: "Scale of the vector field"
        },
        "field_strength" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 2.0,
          description: "Strength of the field forces"
        },
        "field_evolution" => %{
          type: :float,
          default: 0.2,
          min: 0.0,
          max: 1.0,
          description: "Speed of field evolution over time"
        },
        "particle_speed" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 2.0,
          description: "Base speed of particles"
        },
        "tail_length" => %{
          type: :integer,
          default: 5,
          min: 0,
          max: 10,
          description: "Length of particle trails"
        }
      }
    }
  end

  @impl true
  def init(params) do
    # Get parameters with defaults
    particle_count = PatternHelpers.get_param(params, "particle_count", 40, :integer)

    state = %{
      width: @default_width,
      height: @default_height,
      # Global parameters
      brightness: PatternHelpers.get_param(params, "brightness", 1.0, :float),
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "rainbow", :string),
      speed: PatternHelpers.get_param(params, "speed", 1.0, :float),
      # Pattern-specific parameters
      field_type: PatternHelpers.get_param(params, "field_type", "perlin", :string),
      particle_count: particle_count,
      field_scale: PatternHelpers.get_param(params, "field_scale", 0.1, :float),
      field_strength: PatternHelpers.get_param(params, "field_strength", 1.0, :float),
      field_evolution: PatternHelpers.get_param(params, "field_evolution", 0.2, :float),
      particle_speed: PatternHelpers.get_param(params, "particle_speed", 0.5, :float),
      tail_length: PatternHelpers.get_param(params, "tail_length", 5, :integer),
      # Animation state
      time: 0.0,
      # Initialize particles
      particles: init_particles(@default_width, @default_height, particle_count)
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time - apply speed multiplier from global parameters
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update particles based on the vector field
    updated_particles = update_particles(
      state.particles,
      state.width,
      state.height,
      time,
      state.field_type,
      state.field_scale,
      state.field_strength,
      state.field_evolution,
      state.particle_speed,
      state.tail_length,
      delta_time
    )

    # Generate pixels for the frame
    pixels = render_pixels(
      state.width,
      state.height,
      updated_particles,
      time,
      state.tail_length,
      state.brightness,
      state.color_scheme
    )

    # Create the frame
    frame = Frame.new("flow_field", state.width, state.height, pixels)

    # Update state
    new_state = %{state |
      time: time,
      particles: updated_particles
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Get new particle count
    new_particle_count = PatternHelpers.get_param(params, "particle_count", state.particle_count, :integer)

    # Reinitialize particles if count changes
    particles = if new_particle_count != state.particle_count do
      init_particles(state.width, state.height, new_particle_count)
    else
      state.particles
    end

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      field_type: PatternHelpers.get_param(params, "field_type", state.field_type, :string),
      particle_count: new_particle_count,
      field_scale: PatternHelpers.get_param(params, "field_scale", state.field_scale, :float),
      field_strength: PatternHelpers.get_param(params, "field_strength", state.field_strength, :float),
      field_evolution: PatternHelpers.get_param(params, "field_evolution", state.field_evolution, :float),
      particle_speed: PatternHelpers.get_param(params, "particle_speed", state.particle_speed, :float),
      tail_length: PatternHelpers.get_param(params, "tail_length", state.tail_length, :integer),
      particles: particles
    }

    {:ok, updated_state}
  end

  # Initialize particles with random positions
  defp init_particles(width, height, count) do
    Enum.map(1..count, fn i ->
      # Random position within grid bounds
      x = :rand.uniform() * (width - 1)
      y = :rand.uniform() * (height - 1)

      # Random hue for particle color
      hue = i / count

      %{
        x: x,
        y: y,
        hue: hue,
        history: [],  # For tracking trail positions
        age: :rand.uniform() * 100  # Random starting age for varied initial state
      }
    end)
  end

  # Update particles based on vector field
  defp update_particles(particles, width, height, time, field_type, field_scale,
                       field_strength, field_evolution, particle_speed, tail_length, delta_time) do
    particles
    |> Enum.map(fn particle ->
      # Calculate vector field at particle position
      {dx, dy} = calculate_vector_field(
        particle.x,
        particle.y,
        time,
        field_type,
        field_scale,
        field_strength,
        field_evolution
      )

      # Update position based on field vector
      new_x = particle.x + dx * particle_speed * delta_time
      new_y = particle.y + dy * particle_speed * delta_time

      # Handle boundary conditions (wrap around)
      new_x = cond do
        new_x < 0 -> new_x + width
        new_x >= width -> new_x - width
        true -> new_x
      end

      new_y = cond do
        new_y < 0 -> new_y + height
        new_y >= height -> new_y - height
        true -> new_y
      end

      # Add current position to history for trails
      # Convert to integers for rendering
      current_pos = {trunc(particle.x), trunc(particle.y)}
      new_history = [current_pos | particle.history] |> Enum.take(tail_length)

      # Update particle
      %{
        x: new_x,
        y: new_y,
        hue: particle.hue,
        history: new_history,
        age: particle.age + delta_time
      }
    end)
  end

  # Calculate vector field at a position
  defp calculate_vector_field(x, y, time, field_type, field_scale, field_strength, field_evolution) do
    # Apply time factor for field evolution
    time_factor = time * field_evolution

    case field_type do
      "perlin" ->
        # Perlin noise based field
        # Simple approximation using sine functions at different frequencies
        noise_x = :math.sin(x * field_scale + time_factor * 0.3) *
                  :math.cos(y * field_scale * 1.5 + time_factor * 0.2)
        noise_y = :math.cos(x * field_scale * 1.7 + time_factor * 0.1) *
                  :math.sin(y * field_scale + time_factor * 0.4)

        {noise_x * field_strength, noise_y * field_strength}

      "circular" ->
        # Circular/vortex flow
        # Calculate normalized vector from center
        center_x = x - 12.5  # Assuming center at about half width
        center_y = y - 12.0  # Assuming center at about half height
        dist = :math.sqrt(center_x * center_x + center_y * center_y)
        dist = max(dist, 0.1)  # Avoid division by zero

        # Rotate 90 degrees for circular motion and add some time-based variation
        rotation_factor = 1.0 + :math.sin(time_factor) * 0.2
        {-center_y / dist * field_strength * rotation_factor,
         center_x / dist * field_strength * rotation_factor}

      "sine_wave" ->
        # Sine wave based flow
        wave_x = :math.sin(y * field_scale + time_factor)
        wave_y = :math.cos(x * field_scale + time_factor * 0.7)

        {wave_x * field_strength, wave_y * field_strength}

      "attractor" ->
        # Strange attractor inspired
        # Simplified Lorenz attractor influence
        dx = :math.sin(y * field_scale) + :math.cos(time_factor * 0.2)
        dy = :math.sin(x * field_scale * 0.8) * :math.cos(y * field_scale * 0.5 + time_factor * 0.3)

        {dx * field_strength, dy * field_strength}

      _ ->
        # Default to simple circular field if unknown type
        {-y * 0.1 * field_strength, x * 0.1 * field_strength}
    end
  end

  # Helper function to render pixels
  defp render_pixels(width, height, particles, time, tail_length, brightness, color_scheme) do
    # Initialize black canvas
    canvas = for _y <- 0..(height - 1), _x <- 0..(width - 1), do: {0, 0, 0}

    # Draw particles and their trails
    particles
    |> Enum.reduce(canvas, fn particle, acc_canvas ->
      # Draw the particle head
      head_x = trunc(particle.x)
      head_y = trunc(particle.y)

      # Color based on particle hue and position
      base_color = PatternHelpers.rem_float(particle.hue + time * 0.05, 1.0)

      # Draw head with full brightness
      acc_canvas = update_pixel(acc_canvas, head_x, head_y, base_color, brightness, color_scheme, width, height)

      # Draw trail with decreasing brightness
      particle.history
      |> Enum.with_index()
      |> Enum.reduce(acc_canvas, fn {{trail_x, trail_y}, idx}, trail_canvas ->
        # Calculate diminishing brightness based on position in trail
        trail_brightness = brightness * (1.0 - idx / (tail_length + 1))

        # Slight color shift along trail
        trail_color = PatternHelpers.rem_float(base_color - idx * 0.02, 1.0)

        update_pixel(trail_canvas, trail_x, trail_y, trail_color, trail_brightness, color_scheme, width, height)
      end)
    end)
  end

  # Helper to update a single pixel while respecting bounds
  defp update_pixel(canvas, x, y, color_value, brightness, color_scheme, width, height) do
    if x >= 0 and x < width and y >= 0 and y < height do
      {r, g, b} = PatternHelpers.get_color(color_scheme, color_value, brightness)
      index = y * width + x
      List.replace_at(canvas, index, {r, g, b})
    else
      canvas
    end
  end
end
