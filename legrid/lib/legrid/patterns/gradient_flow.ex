defmodule Legrid.Patterns.GradientFlow do
  @moduledoc """
  Pattern generator for fluid-like gradient flow.

  Creates smooth, evolving color fields that move like a fluid with vortices,
  currents, and swirls. The colors flow organically across the grid creating
  a mesmerizing display of gradients in motion.
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
      id: "gradient_flow",
      name: "Gradient Flow",
      description: "Fluid-like flowing color gradients with organic movement",
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
          description: "Flow animation speed"
        },
        # Pattern-specific parameters
        "flow_complexity" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 1.0,
          description: "Complexity of the flow pattern"
        },
        "vortex_strength" => %{
          type: :float,
          default: 0.7,
          min: 0.0,
          max: 1.0,
          description: "Strength of vortices in the flow"
        },
        "color_contrast" => %{
          type: :float,
          default: 0.8,
          min: 0.1,
          max: 1.0,
          description: "Contrast between colors in the flow"
        },
        "flow_mode" => %{
          type: :enum,
          default: "fluid",
          options: ["fluid", "magnetic", "thermal", "electric"],
          description: "Type of flow simulation to use"
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
      flow_complexity: PatternHelpers.get_param(params, "flow_complexity", 0.5, :float),
      vortex_strength: PatternHelpers.get_param(params, "vortex_strength", 0.7, :float),
      color_contrast: PatternHelpers.get_param(params, "color_contrast", 0.8, :float),
      flow_mode: PatternHelpers.get_param(params, "flow_mode", "fluid", :string),
      # Animation state
      time: 0.0,
      # Initialize fluid simulation fields
      velocity_field: initialize_velocity_field(@default_width, @default_height),
      color_field: initialize_color_field(@default_width, @default_height),
      # Vortex centers
      vortices: generate_vortices(@default_width, @default_height, 3)
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds
    delta_time = elapsed_ms / 1000.0 * state.speed * 0.5
    time = state.time + delta_time

    # Update velocity field
    velocity_field = update_velocity_field(
      state.velocity_field,
      state.vortices,
      state.width,
      state.height,
      time,
      state.vortex_strength,
      state.flow_complexity,
      state.flow_mode
    )

    # Advect (move) the color field through the velocity field
    color_field = advect_color_field(
      state.color_field,
      velocity_field,
      state.width,
      state.height,
      delta_time
    )

    # Occasionally add new color sources
    color_field = if :rand.uniform() < delta_time * 0.2 do
      add_color_sources(color_field, state.width, state.height, time)
    else
      color_field
    end

    # Diffuse the color field to smooth it out
    color_field = diffuse_color_field(color_field, state.width, state.height, delta_time * 0.5)

    # Generate pixels for the frame based on the color field
    pixels = render_color_field(
      color_field,
      state.width,
      state.height,
      time,
      state.color_scheme,
      state.brightness,
      state.color_contrast
    )

    # Create the frame
    frame = Frame.new("gradient_flow", state.width, state.height, pixels)

    # Update state with new time and fields
    new_state = %{state |
      time: time,
      velocity_field: velocity_field,
      color_field: color_field
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      flow_complexity: PatternHelpers.get_param(params, "flow_complexity", state.flow_complexity, :float),
      vortex_strength: PatternHelpers.get_param(params, "vortex_strength", state.vortex_strength, :float),
      color_contrast: PatternHelpers.get_param(params, "color_contrast", state.color_contrast, :float),
      flow_mode: PatternHelpers.get_param(params, "flow_mode", state.flow_mode, :string)
    }

    # Reset vortices if significant parameter change
    updated_state = if Map.has_key?(params, "flow_complexity") or Map.has_key?(params, "flow_mode") do
      %{updated_state | vortices: generate_vortices(state.width, state.height, 3)}
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Initialize velocity field (vector field)
  defp initialize_velocity_field(width, height) do
    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      # Initially zero velocity
      {{x, y}, {0.0, 0.0}}
    end
  end

  # Initialize color field (scalar field)
  defp initialize_color_field(width, height) do
    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      # Initialize with small random values
      {{x, y}, :rand.uniform() * 0.1}
    end
  end

  # Generate random vortex centers
  defp generate_vortices(width, height, count) do
    for _ <- 1..count do
      %{
        x: :rand.uniform() * width,
        y: :rand.uniform() * height,
        strength: (:rand.uniform() * 2 - 1), # Positive or negative rotation
        radius: 2 + :rand.uniform() * 5,     # Influence radius
        drift_x: (:rand.uniform() * 2 - 1) * 0.2, # Slow drift
        drift_y: (:rand.uniform() * 2 - 1) * 0.2
      }
    end
  end

  # Update the velocity field based on vortices and flow model
  defp update_velocity_field(field, vortices, width, height, time, vortex_strength, complexity, flow_mode) do
    # Time-based evolution factor
    time_factor = :math.sin(time * 0.2) * 0.3 + 0.7

    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      # Base value using perlin-like noise for general flow
      angle = generate_flow_angle(x, y, width, height, time, complexity, flow_mode)
      base_speed = 0.5 + :math.sin(time * 0.3 + x * 0.1 + y * 0.1) * 0.2

      # Base vector from angle
      vx = :math.cos(angle) * base_speed
      vy = :math.sin(angle) * base_speed

      # Apply vortex influence
      {vx, vy} = Enum.reduce(vortices, {vx, vy}, fn vortex, {curr_vx, curr_vy} ->
        # Update vortex position with time (drifting)
        vortex_x = vortex.x + :math.sin(time * 0.1) * vortex.drift_x * width
        vortex_y = vortex.y + :math.cos(time * 0.1) * vortex.drift_y * height

        # Calculate distance to vortex
        dx = x - vortex_x
        dy = y - vortex_y
        distance = :math.sqrt(dx * dx + dy * dy)

        # Vortex strength falls off with distance
        factor = vortex_strength * time_factor * vortex.strength *
                 :math.exp(-distance / vortex.radius)

        # Add rotational component (perpendicular to radius)
        {curr_vx - dy * factor, curr_vy + dx * factor}
      end)

      # Store result in field
      {{x, y}, {vx, vy}}
    end
  end

  # Generate flow angle based on position and time
  defp generate_flow_angle(x, y, width, height, time, complexity, flow_mode) do
    # Normalize coordinates
    nx = x / width
    ny = y / height

    # Time-based variations
    t1 = time * 0.1
    t2 = time * 0.05

    # Different flow patterns based on mode
    case flow_mode do
      "fluid" ->
        # Fluid-like flow with multiple frequencies
        :math.sin(nx * 5 * complexity + t1) *
        :math.cos(ny * 3 * complexity + t2) *
        :math.pi * 2

      "magnetic" ->
        # Magnetic field-like pattern
        distance_from_center = :math.sqrt(:math.pow(nx - 0.5, 2) + :math.pow(ny - 0.5, 2))
        :math.atan2(ny - 0.5, nx - 0.5) +
        distance_from_center * 5 * complexity +
        time * 0.2

      "thermal" ->
        # Thermal convection cells
        cell_size = 0.1 + complexity * 0.2
        cell_x = rem_float(nx, cell_size) / cell_size
        cell_y = rem_float(ny, cell_size) / cell_size
        :math.atan2(cell_y - 0.5, cell_x - 0.5) + time * 0.3

      "electric" ->
        # Electric field-like pattern with multiple poles
        poles = [
          {0.3, 0.3, :math.sin(time * 0.2)},
          {0.7, 0.7, -:math.sin(time * 0.2)},
          {0.3, 0.7, :math.cos(time * 0.3)},
          {0.7, 0.3, -:math.cos(time * 0.3)}
        ]

        # Sum influence from each pole
        {fx, fy} = Enum.reduce(poles, {0.0, 0.0}, fn {px, py, charge}, {fx, fy} ->
          dx = nx - px
          dy = ny - py
          dist = :math.sqrt(dx * dx + dy * dy) + 0.01  # Avoid division by zero
          strength = charge / (dist * dist) * complexity
          {fx + dx * strength, fy + dy * strength}
        end)

        :math.atan2(fy, fx)
    end
  end

  # Advect (move) the color field through the velocity field
  defp advect_color_field(color_field, velocity_field, width, height, dt) do
    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      pos = {x, y}

      # Get velocity at this position
      {vx, vy} = Map.get(velocity_field, pos, {0.0, 0.0})

      # Trace back to find where this color came from
      src_x = x - vx * dt * 2
      src_y = y - vy * dt * 2

      # Interpolate from the color field
      color_value = sample_color_field(color_field, src_x, src_y, width, height)

      # Small amount of dissipation
      dissipation = 0.995
      {pos, color_value * dissipation}
    end
  end

  # Sample from the color field using bilinear interpolation
  defp sample_color_field(field, x, y, width, height) do
    # Ensure coordinates wrap around the edges
    x = rem_float(x, width)
    y = rem_float(y, height)

    # Get integer coordinates
    x0 = :math.floor(x)
    y0 = :math.floor(y)
    x1 = rem(trunc(x0) + 1, width)
    y1 = rem(trunc(y0) + 1, height)

    # Get fractional part
    fx = x - x0
    fy = y - y0

    # Get the four nearest points
    c00 = Map.get(field, {trunc(x0), trunc(y0)}, 0.0)
    c10 = Map.get(field, {trunc(x1), trunc(y0)}, 0.0)
    c01 = Map.get(field, {trunc(x0), trunc(y1)}, 0.0)
    c11 = Map.get(field, {trunc(x1), trunc(y1)}, 0.0)

    # Bilinear interpolation
    c0 = c00 * (1 - fx) + c10 * fx
    c1 = c01 * (1 - fx) + c11 * fx
    c0 * (1 - fy) + c1 * fy
  end

  # Add new color sources to the field
  defp add_color_sources(field, width, height, time) do
    # Add 1-3 new color sources
    count = :rand.uniform(3)

    Enum.reduce(1..count, field, fn _, acc ->
      # Random position
      x = :rand.uniform(width - 1)
      y = :rand.uniform(height - 1)

      # Add a color source with time-based value
      strength = 0.5 + :math.sin(time * 0.3) * 0.3
      radius = 1 + :rand.uniform() * 2

      # Apply the source to nearby points
      Enum.reduce(-3..3, acc, fn dy, acc_y ->
        Enum.reduce(-3..3, acc_y, fn dx, acc_xy ->
          px = rem(x + dx + width, width)
          py = rem(y + dy + height, height)

          distance = :math.sqrt(dx * dx + dy * dy)
          if distance <= radius do
            intensity = strength * (1 - distance / radius)
            pos = {px, py}
            current = Map.get(acc_xy, pos, 0.0)
            Map.put(acc_xy, pos, current + intensity)
          else
            acc_xy
          end
        end)
      end)
    end)
  end

  # Diffuse the color field
  defp diffuse_color_field(field, width, height, dt) do
    # Simple box blur diffusion
    alpha = dt * 0.2  # Diffusion rate

    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      pos = {x, y}
      current = Map.get(field, pos, 0.0)

      # Sample neighbors
      sum = for dy <- -1..1, dx <- -1..1, dx != 0 or dy != 0 do
        nx = rem(x + dx + width, width)
        ny = rem(y + dy + height, height)
        Map.get(field, {nx, ny}, 0.0)
      end
      |> Enum.sum()

      # Mix with neighbors
      avg = sum / 8
      {pos, current * (1 - alpha) + avg * alpha}
    end
  end

  # Render the color field to pixels
  defp render_color_field(field, width, height, time, color_scheme, brightness, contrast) do
    for y <- 0..(height-1), x <- 0..(width-1) do
      # Get color value at this position
      base_value = Map.get(field, {x, y}, 0.0)

      # Apply contrast
      value = 0.5 + (base_value - 0.5) * contrast

      # Clamp to valid range
      value = max(0.0, min(1.0, value))

      # Time-based color variation
      color_value = PatternHelpers.rem_float(value + time * 0.05, 1.0)

      # Get final color
      PatternHelpers.get_color(color_scheme, color_value, value * brightness)
    end
  end

  # Floating point remainder helper
  defp rem_float(a, b) do
    a - b * :math.floor(a / b)
  end
end
