defmodule Legrid.Patterns.AttractorTracer do
  @moduledoc """
  Pattern generator for mathematical strange attractors.

  Visualizes various strange attractors (Lorenz, Rössler, etc.)
  with particle trails and slowly evolving parameters.
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
      id: "attractor_tracer",
      name: "Attractor Tracer",
      description: "Mathematical strange attractors with evolving parameters",
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
        "attractor_type" => %{
          type: :enum,
          default: "lorenz",
          options: ["lorenz", "rossler", "aizawa", "thomas", "chen"],
          description: "Type of strange attractor"
        },
        "trail_length" => %{
          type: :integer,
          default: 200,
          min: 50,
          max: 500,
          description: "Length of particle trails"
        },
        "parameter_evolution" => %{
          type: :float,
          default: 0.3,
          min: 0.0,
          max: 1.0,
          description: "Rate of parameter evolution over time"
        },
        "particle_count" => %{
          type: :integer,
          default: 3,
          min: 1,
          max: 10,
          description: "Number of particles to trace"
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
      attractor_type: PatternHelpers.get_param(params, "attractor_type", "lorenz", :string),
      trail_length: PatternHelpers.get_param(params, "trail_length", 200, :integer),
      parameter_evolution: PatternHelpers.get_param(params, "parameter_evolution", 0.3, :float),
      particle_count: PatternHelpers.get_param(params, "particle_count", 3, :integer),
      # Animation state
      time: 0.0,
      particles: [],
      # Attractor parameters (default values - will be overridden)
      attractor_params: %{},
      # Scale factor for mapping attractor coordinates to grid
      scale: 1.0
    }

    # Initialize particles and parameters based on attractor type
    state = initialize_attractor(state)

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time
    delta_time = elapsed_ms / 1000.0 * state.speed * 0.2
    time = state.time + delta_time

    # Update attractor parameters if parameter evolution is enabled
    attractor_params = if state.parameter_evolution > 0 do
      evolve_parameters(state.attractor_params, state.attractor_type, time, state.parameter_evolution)
    else
      state.attractor_params
    end

    # Update particle positions
    particles = update_particles(
      state.particles,
      state.attractor_type,
      attractor_params,
      delta_time * 5.0,
      state.trail_length
    )

    # Generate pixels for the frame
    pixels = render_particles(
      particles,
      state.width,
      state.height,
      time,
      state.scale,
      state.color_scheme,
      state.brightness
    )

    # Create the frame
    frame = Frame.new("attractor_tracer", state.width, state.height, pixels)

    # Update state
    new_state = %{state |
      time: time,
      particles: particles,
      attractor_params: attractor_params
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Check if we need to reinitialize (attractor type changed)
    reinitialize = Map.has_key?(params, "attractor_type")

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      attractor_type: PatternHelpers.get_param(params, "attractor_type", state.attractor_type, :string),
      trail_length: PatternHelpers.get_param(params, "trail_length", state.trail_length, :integer),
      parameter_evolution: PatternHelpers.get_param(params, "parameter_evolution", state.parameter_evolution, :float),
      particle_count: PatternHelpers.get_param(params, "particle_count", state.particle_count, :integer)
    }

    # Reinitialize if needed
    updated_state = if reinitialize do
      initialize_attractor(updated_state)
    else
      # Update particle count if it changed
      if Map.has_key?(params, "particle_count") && state.particle_count != updated_state.particle_count do
        # Keep existing particles if decreasing, add more if increasing
        if updated_state.particle_count < state.particle_count do
          %{updated_state | particles: Enum.take(state.particles, updated_state.particle_count)}
        else
          additional_count = updated_state.particle_count - state.particle_count
          additional_particles = initialize_particles(
            updated_state.attractor_type,
            additional_count,
            updated_state.trail_length
          )
          %{updated_state | particles: state.particles ++ additional_particles}
        end
      else
        # Update trail length if it changed
        if Map.has_key?(params, "trail_length") do
          particles = Enum.map(state.particles, fn particle ->
            points = Enum.take(particle.points, min(length(particle.points), updated_state.trail_length))
            %{particle | points: points}
          end)
          %{updated_state | particles: particles}
        else
          updated_state
        end
      end
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Initialize attractor based on type
  defp initialize_attractor(state) do
    # Set up parameters based on attractor type
    attractor_params = case state.attractor_type do
      "lorenz" -> %{
        sigma: 10.0,
        rho: 28.0,
        beta: 8.0 / 3.0,
        scale: 0.05
      }
      "rossler" -> %{
        a: 0.2,
        b: 0.2,
        c: 5.7,
        scale: 0.1
      }
      "aizawa" -> %{
        a: 0.95,
        b: 0.7,
        c: 0.6,
        d: 3.5,
        e: 0.25,
        f: 0.1,
        scale: 0.2
      }
      "thomas" -> %{
        b: 0.208186,
        scale: 0.25
      }
      "chen" -> %{
        a: 5.0,
        b: -10.0,
        c: -0.38,
        scale: 0.1
      }
    end

    # Get scale from parameters
    scale = Map.get(attractor_params, :scale, 1.0)

    # Initialize particles
    particles = initialize_particles(state.attractor_type, state.particle_count, state.trail_length)

    # Update state
    %{state |
      attractor_params: attractor_params,
      particles: particles,
      scale: scale
    }
  end

  # Initialize particles with random starting positions
  defp initialize_particles(attractor_type, count, trail_length) do
    for i <- 1..count do
      # Random starting position depending on attractor type
      start_pos = case attractor_type do
        "lorenz" -> {
          :rand.normal() * 0.1,
          :rand.normal() * 0.1,
          :rand.normal() * 0.1 + 20
        }
        "rossler" -> {
          :rand.normal() * 0.1 + 1,
          :rand.normal() * 0.1,
          :rand.normal() * 0.1
        }
        "aizawa" -> {
          :rand.normal() * 0.1 + 0.5,
          :rand.normal() * 0.1,
          :rand.normal() * 0.1
        }
        "thomas" -> {
          :rand.normal() * 0.1 + 1,
          :rand.normal() * 0.1 + 1,
          :rand.normal() * 0.1 + 1
        }
        "chen" -> {
          :rand.normal() * 0.1 + 5,
          :rand.normal() * 0.1 + 5,
          :rand.normal() * 0.1 + 15
        }
      end

      # Random color offset
      color_offset = i / count

      %{
        points: List.duplicate(start_pos, 1),  # Start with just one point
        color_offset: color_offset
      }
    end
  end

  # Update particle positions based on attractor equations
  defp update_particles(particles, attractor_type, params, dt, trail_length) do
    Enum.map(particles, fn particle ->
      # Get current position (last point in the trail)
      {x, y, z} = List.last(particle.points)

      # Calculate new position based on attractor type
      new_point = case attractor_type do
        "lorenz" -> update_lorenz(x, y, z, dt, params)
        "rossler" -> update_rossler(x, y, z, dt, params)
        "aizawa" -> update_aizawa(x, y, z, dt, params)
        "thomas" -> update_thomas(x, y, z, dt, params)
        "chen" -> update_chen(x, y, z, dt, params)
      end

      # Add new point to trail and limit trail length
      new_points = (particle.points ++ [new_point])
                  |> Enum.take(-trail_length)

      %{particle | points: new_points}
    end)
  end

  # Lorenz attractor update equations
  defp update_lorenz(x, y, z, dt, params) do
    dx = params.sigma * (y - x)
    dy = x * (params.rho - z) - y
    dz = x * y - params.beta * z

    {
      x + dx * dt,
      y + dy * dt,
      z + dz * dt
    }
  end

  # Rössler attractor update equations
  defp update_rossler(x, y, z, dt, params) do
    dx = -y - z
    dy = x + params.a * y
    dz = params.b + z * (x - params.c)

    {
      x + dx * dt,
      y + dy * dt,
      z + dz * dt
    }
  end

  # Aizawa attractor update equations
  defp update_aizawa(x, y, z, dt, params) do
    dx = (z - params.b) * x - params.d * y
    dy = params.d * x + (z - params.b) * y
    dz = params.c + params.a * z - z * z * z / 3 - (x * x + y * y) * (1 + params.e * z) + params.f * z * x * x * x

    {
      x + dx * dt,
      y + dy * dt,
      z + dz * dt
    }
  end

  # Thomas attractor update equations
  defp update_thomas(x, y, z, dt, params) do
    dx = -params.b * x + :math.sin(y)
    dy = -params.b * y + :math.sin(z)
    dz = -params.b * z + :math.sin(x)

    {
      x + dx * dt,
      y + dy * dt,
      z + dz * dt
    }
  end

  # Chen attractor update equations
  defp update_chen(x, y, z, dt, params) do
    dx = params.a * (y - x)
    dy = (params.c - params.a) * x - x * z + params.c * y
    dz = x * y + params.b * z

    {
      x + dx * dt,
      y + dy * dt,
      z + dz * dt
    }
  end

  # Evolve attractor parameters over time for more dynamic visuals
  defp evolve_parameters(params, attractor_type, time, evolution_rate) do
    case attractor_type do
      "lorenz" ->
        # Slowly vary the rho parameter
        rho_variation = 28.0 + :math.sin(time * 0.1 * evolution_rate) * 4.0
        %{params | rho: rho_variation}

      "rossler" ->
        # Vary the c parameter
        c_variation = 5.7 + :math.sin(time * 0.05 * evolution_rate) * 1.0
        %{params | c: c_variation}

      "aizawa" ->
        # Vary the a and e parameters
        a_variation = 0.95 + :math.sin(time * 0.1 * evolution_rate) * 0.1
        e_variation = 0.25 + :math.cos(time * 0.08 * evolution_rate) * 0.05
        %{params | a: a_variation, e: e_variation}

      "thomas" ->
        # Vary the b parameter
        b_variation = 0.208186 + :math.sin(time * 0.03 * evolution_rate) * 0.01
        %{params | b: b_variation}

      "chen" ->
        # Vary the a parameter
        a_variation = 5.0 + :math.sin(time * 0.05 * evolution_rate) * 1.0
        %{params | a: a_variation}
    end
  end

  # Render particles and trails to the LED grid
  defp render_particles(particles, width, height, time, scale, color_scheme, brightness) do
    # Create an empty black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Center offset
    offset_x = width / 2
    offset_y = height / 2

    # Draw all particles on the canvas
    Enum.reduce(particles, canvas, fn particle, acc ->
      # Draw the particle's trail
      points = particle.points

      # Draw each point in the trail with graduated brightness
      Enum.with_index(points)
      |> Enum.reduce(acc, fn {{x, y, z}, idx}, canvas_acc ->
        # Map 3D coordinates to 2D grid
        # Use perspective projection with z affecting the scale
        perspective = 1.0 / (1.0 + z * 0.05)
        grid_x = trunc(offset_x + (x * scale * perspective))
        grid_y = trunc(offset_y + (y * scale * perspective))

        # Skip if outside grid
        if grid_x >= 0 && grid_x < width && grid_y >= 0 && grid_y < height do
          # Calculate brightness based on position in trail
          # Newer points are brighter
          age_factor = idx / length(points)
          point_brightness = (1.0 - age_factor) * brightness

          # Calculate color value based on position and particle offset
          # z-coordinate and time influence color
          color_value = PatternHelpers.rem_float(
            particle.color_offset + z * 0.01 + time * 0.1,
            1.0
          )

          # Get the color
          color = PatternHelpers.get_color(color_scheme, color_value, point_brightness)

          # Calculate index in the flattened canvas
          index = grid_y * width + grid_x

          # Combine with existing color (brightest wins)
          {r1, g1, b1} = Enum.at(canvas_acc, index)
          {r2, g2, b2} = color

          # Choose brighter color
          brightness1 = r1 + g1 + b1
          brightness2 = r2 + g2 + b2

          new_color = if brightness2 > brightness1, do: color, else: {r1, g1, b1}

          # Update the canvas
          List.replace_at(canvas_acc, index, new_color)
        else
          canvas_acc
        end
      end)
    end)
  end
end
