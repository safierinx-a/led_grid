defmodule Legrid.Patterns.VoronoiCells do
  @moduledoc """
  Pattern generator for Voronoi cell visualizations.

  Creates dynamic cellular regions where each pixel is colored based on its
  nearest "seed" point. Seeds can move around creating flowing, organic
  boundaries between colored regions.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.{PatternHelpers, SpatialHelpers}

  @default_width 25
  @default_height 24

  @impl true
  def metadata do
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "voronoi_cells",
      name: "Voronoi Cells",
      description: "Dynamic cellular regions with flowing boundaries and moving seed points",
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
        "seed_count" => %{
          type: :integer,
          default: 5,
          min: 2,
          max: 12,
          description: "Number of seed points"
        },
        "movement_style" => %{
          type: :enum,
          default: "orbital",
          options: ["orbital", "random_walk", "bouncing", "spiral", "linear"],
          description: "How seeds move around the grid"
        },
        "distance_fade" => %{
          type: :float,
          default: 0.3,
          min: 0.0,
          max: 1.0,
          description: "How much colors fade with distance from seed"
        },
        "boundary_width" => %{
          type: :float,
          default: 0.1,
          min: 0.0,
          max: 0.5,
          description: "Width of highlighted cell boundaries"
        },
        "color_mode" => %{
          type: :enum,
          default: "per_seed",
          options: ["per_seed", "distance_based", "mixed"],
          description: "How colors are assigned to cells"
        },
        "boundary_highlight" => %{
          type: :boolean,
          default: true,
          description: "Whether to highlight cell boundaries"
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
      seed_count: PatternHelpers.get_param(params, "seed_count", 5, :integer),
      movement_style: PatternHelpers.get_param(params, "movement_style", "orbital", :string),
      distance_fade: PatternHelpers.get_param(params, "distance_fade", 0.3, :float),
      boundary_width: PatternHelpers.get_param(params, "boundary_width", 0.1, :float),
      color_mode: PatternHelpers.get_param(params, "color_mode", "per_seed", :string),
      boundary_highlight: PatternHelpers.get_param(params, "boundary_highlight", true, :boolean),
      # Animation state
      time: 0.0,
      seeds: initialize_seeds(@default_width, @default_height,
                             PatternHelpers.get_param(params, "seed_count", 5, :integer),
                             PatternHelpers.get_param(params, "movement_style", "orbital", :string))
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    frame = %Frame{
      width: state.width,
      height: state.height,
      pixels: []
    }

    time = elapsed_ms / 1000.0

    # Update seed positions
    updated_seeds = update_seed_positions(state.seeds, time, state.speed,
                                         state.movement_style, state.width, state.height)

    # For each pixel, find nearest seed and calculate color
    pixels = for y <- 0..(state.height-1) do
      for x <- 0..(state.width-1) do
        pixel_pos = {x, y}

        # Find nearest seed and distance
        {nearest_seed, min_distance, second_distance} = find_nearest_seeds(pixel_pos, updated_seeds)

        # Calculate if we're near a boundary
        boundary_factor = if state.boundary_highlight do
          calculate_boundary_factor(min_distance, second_distance, state.boundary_width)
        else
          0.0
        end

        # Calculate color based on mode
        base_color = case state.color_mode do
          "per_seed" ->
            seed_color_value = nearest_seed.color_offset
            PatternHelpers.get_color(state.color_scheme, seed_color_value, 1.0)

          "distance_based" ->
            # Color based on distance from seed
            max_dist = SpatialHelpers.max_dimension(frame) / 2
            distance_ratio = min(min_distance / max_dist, 1.0)
            PatternHelpers.get_color(state.color_scheme, distance_ratio, 1.0)

          "mixed" ->
            # Blend seed color with distance-based color
            seed_color_value = nearest_seed.color_offset
            max_dist = SpatialHelpers.max_dimension(frame) / 2
            distance_ratio = min(min_distance / max_dist, 1.0)
            blended_value = (seed_color_value + distance_ratio) / 2
            PatternHelpers.get_color(state.color_scheme, blended_value, 1.0)
        end

        # Apply distance fade
        distance_brightness = if state.distance_fade > 0 do
          max_dist = SpatialHelpers.max_dimension(frame) / 2
          distance_ratio = min(min_distance / max_dist, 1.0)
          1.0 - (distance_ratio * state.distance_fade)
        else
          1.0
        end

        # Apply boundary highlight
        boundary_brightness = if boundary_factor > 0 do
          1.0 + boundary_factor * 0.5  # Brighten boundaries
        else
          distance_brightness
        end

        # Final color calculation
        final_brightness = boundary_brightness * state.brightness
        apply_brightness_to_color(base_color, final_brightness)
      end
    end
    |> List.flatten()

    {:ok, %{frame | pixels: pixels}, %{state | seeds: updated_seeds, time: time}}
  end

  @impl true
  def update_params(state, params) do
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Check if seed count changed
    new_seed_count = PatternHelpers.get_param(params, "seed_count", state.seed_count, :integer)
    new_movement_style = PatternHelpers.get_param(params, "movement_style", state.movement_style, :string)

    # Reinitialize seeds if count or movement style changed
    seeds = if new_seed_count != state.seed_count or new_movement_style != state.movement_style do
      initialize_seeds(state.width, state.height, new_seed_count, new_movement_style)
    else
      state.seeds
    end

    updated_state = %{updated_state |
      seed_count: new_seed_count,
      movement_style: new_movement_style,
      distance_fade: PatternHelpers.get_param(params, "distance_fade", state.distance_fade, :float),
      boundary_width: PatternHelpers.get_param(params, "boundary_width", state.boundary_width, :float),
      color_mode: PatternHelpers.get_param(params, "color_mode", state.color_mode, :string),
      boundary_highlight: PatternHelpers.get_param(params, "boundary_highlight", state.boundary_highlight, :boolean),
      seeds: seeds
    }

    {:ok, updated_state}
  end

  # Private helper functions

  defp initialize_seeds(width, height, count, movement_style) do
    Enum.map(0..(count-1), fn i ->
      # Distribute seeds evenly around a circle initially
      angle = (i / count) * 2 * :math.pi
      center_x = width / 2
      center_y = height / 2
      radius = min(width, height) / 4

      x = center_x + radius * :math.cos(angle)
      y = center_y + radius * :math.sin(angle)

      %{
        id: i,
        x: x,
        y: y,
        color_offset: i / count,  # Distribute colors evenly
        # Movement parameters
        base_angle: angle,
        movement_phase: :rand.uniform() * 2 * :math.pi,
        movement_speed: 0.8 + :rand.uniform() * 0.4,  # Vary speed slightly
        bounce_dir_x: if(:rand.uniform() > 0.5, do: 1, else: -1),
        bounce_dir_y: if(:rand.uniform() > 0.5, do: 1, else: -1)
      }
    end)
  end

  defp update_seed_positions(seeds, time, speed, movement_style, width, height) do
    Enum.map(seeds, fn seed ->
      case movement_style do
        "orbital" ->
          # Seeds orbit around center points
          center_x = width / 2
          center_y = height / 2
          orbit_radius = min(width, height) / 3
          angle = seed.base_angle + time * speed * seed.movement_speed

          %{seed |
            x: center_x + orbit_radius * :math.cos(angle),
            y: center_y + orbit_radius * :math.sin(angle)
          }

        "spiral" ->
          # Seeds spiral outward and inward
          center_x = width / 2
          center_y = height / 2
          max_radius = min(width, height) / 3
          spiral_time = time * speed * seed.movement_speed + seed.movement_phase
          radius = max_radius * (0.3 + 0.7 * (1 + :math.sin(spiral_time * 0.2)) / 2)
          angle = seed.base_angle + spiral_time

          %{seed |
            x: center_x + radius * :math.cos(angle),
            y: center_y + radius * :math.sin(angle)
          }

        "bouncing" ->
          # Seeds bounce around the boundaries
          bounce_speed = speed * seed.movement_speed * 8
          dx = bounce_speed * seed.bounce_dir_x
          dy = bounce_speed * seed.bounce_dir_y

          new_x = seed.x + dx
          new_y = seed.y + dy

          # Bounce off walls
          {final_x, final_dir_x} = if new_x <= 0 or new_x >= width-1 do
            {max(0, min(width-1, new_x)), -seed.bounce_dir_x}
          else
            {new_x, seed.bounce_dir_x}
          end

          {final_y, final_dir_y} = if new_y <= 0 or new_y >= height-1 do
            {max(0, min(height-1, new_y)), -seed.bounce_dir_y}
          else
            {new_y, seed.bounce_dir_y}
          end

          %{seed |
            x: final_x,
            y: final_y,
            bounce_dir_x: final_dir_x,
            bounce_dir_y: final_dir_y
          }

        "random_walk" ->
          # Seeds perform random walk with drift
          walk_time = time * speed + seed.movement_phase
          drift_x = :math.sin(walk_time * 0.3) * 2
          drift_y = :math.cos(walk_time * 0.2) * 2
          noise_x = (:rand.uniform() - 0.5) * 1.5
          noise_y = (:rand.uniform() - 0.5) * 1.5

          new_x = seed.x + drift_x + noise_x
          new_y = seed.y + drift_y + noise_y

          %{seed |
            x: max(0, min(width-1, new_x)),
            y: max(0, min(height-1, new_y))
          }

        "linear" ->
          # Seeds move in straight lines, wrapping around
          move_time = time * speed * seed.movement_speed
          direction_x = :math.cos(seed.base_angle)
          direction_y = :math.sin(seed.base_angle)

          new_x = PatternHelpers.rem_float(seed.x + direction_x * move_time * 10, width)
          new_y = PatternHelpers.rem_float(seed.y + direction_y * move_time * 10, height)

          %{seed |
            x: new_x,
            y: new_y
          }
      end
    end)
  end

  defp find_nearest_seeds(pos, seeds) do
    {pos_x, pos_y} = pos

    distances = Enum.map(seeds, fn seed ->
      dx = pos_x - seed.x
      dy = pos_y - seed.y
      distance = :math.sqrt(dx * dx + dy * dy)
      {seed, distance}
    end)
    |> Enum.sort_by(fn {_seed, distance} -> distance end)

    [{nearest_seed, min_distance} | rest] = distances
    second_distance = case rest do
      [{_second_seed, dist} | _] -> dist
      [] -> min_distance * 2  # Fallback if only one seed
    end

    {nearest_seed, min_distance, second_distance}
  end

  defp calculate_boundary_factor(min_distance, second_distance, boundary_width) do
    # Calculate how close we are to the boundary between cells
    distance_diff = second_distance - min_distance
    max_boundary_distance = boundary_width * 10  # Scale boundary width

    if distance_diff < max_boundary_distance do
      1.0 - (distance_diff / max_boundary_distance)
    else
      0.0
    end
  end

  defp apply_brightness_to_color({r, g, b}, brightness) do
    {
      trunc(r * brightness),
      trunc(g * brightness),
      trunc(b * brightness)
    }
  end
end
