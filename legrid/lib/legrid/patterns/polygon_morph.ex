defmodule Legrid.Patterns.PolygonMorph do
  @moduledoc """
  Pattern generator for morphing polygon shapes.

  Creates animated transitions between different polygon shapes with
  configurable vertices, morphing styles, and rotation effects.
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
      id: "polygon_morph",
      name: "Polygon Morph",
      description: "Morphing polygons with smooth transitions and effects",
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
        "morph_style" => %{
          type: :enum,
          default: "smooth",
          options: ["smooth", "elastic", "bounce", "wave", "spiral"],
          description: "Style of morphing transition"
        },
        "vertex_count_min" => %{
          type: :integer,
          default: 3,
          min: 3,
          max: 8,
          description: "Minimum number of polygon vertices"
        },
        "vertex_count_max" => %{
          type: :integer,
          default: 6,
          min: 3,
          max: 10,
          description: "Maximum number of polygon vertices"
        },
        "fill_style" => %{
          type: :enum,
          default: "solid",
          options: ["solid", "gradient", "outline", "pulse", "radial"],
          description: "Fill style for the polygons"
        },
        "rotation_enabled" => %{
          type: :boolean,
          default: true,
          description: "Enable rotation effects"
        }
      }
    }
  end

  @impl true
  def init(params) do
    vertex_count_min = PatternHelpers.get_param(params, "vertex_count_min", 3, :integer)
    vertex_count_max = PatternHelpers.get_param(params, "vertex_count_max", 6, :integer)

    # Ensure vertex_count_min <= vertex_count_max
    vertex_count_min = min(vertex_count_min, vertex_count_max)

    state = %{
      width: @default_width,
      height: @default_height,
      # Global parameters
      brightness: PatternHelpers.get_param(params, "brightness", 1.0, :float),
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "rainbow", :string),
      speed: PatternHelpers.get_param(params, "speed", 0.5, :float),
      # Pattern-specific parameters
      morph_style: PatternHelpers.get_param(params, "morph_style", "smooth", :string),
      vertex_count_min: vertex_count_min,
      vertex_count_max: vertex_count_max,
      fill_style: PatternHelpers.get_param(params, "fill_style", "solid", :string),
      rotation_enabled: PatternHelpers.get_param(params, "rotation_enabled", true, :boolean),
      # Animation state
      time: 0.0,
      current_vertices: [],
      target_vertices: [],
      morph_progress: 0.0,
      morph_duration: 3.0,  # seconds
      rotation_angle: 0.0,
      scale: 0.85,          # size relative to display
      current_vertex_count: 0,
      target_vertex_count: 0,
      polygon_center: {0.5, 0.5}, # Normalized center coordinates
      color_offset: 0.0
    }

    # Initialize polygons
    state = initialize_polygons(state)

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update morph progress
    morph_progress = state.morph_progress + delta_time / state.morph_duration

    # Update rotation angle if enabled
    rotation_angle = if state.rotation_enabled do
      state.rotation_angle + delta_time * 0.2
    else
      state.rotation_angle
    end

    # Update color offset
    color_offset = PatternHelpers.rem_float(state.color_offset + delta_time * 0.1, 1.0)

    # Check if we need to generate new target polygon
    {morph_progress, current_vertices, target_vertices, current_vertex_count, target_vertex_count} =
      if morph_progress >= 1.0 do
        # Move to the next morph target
        {
          0.0,
          state.target_vertices,
          generate_polygon(state.target_vertex_count, state.vertex_count_min, state.vertex_count_max),
          state.target_vertex_count,
          select_next_vertex_count(state.target_vertex_count, state.vertex_count_min, state.vertex_count_max)
        }
      else
        {
          morph_progress,
          state.current_vertices,
          state.target_vertices,
          state.current_vertex_count,
          state.target_vertex_count
        }
      end

    # Calculate morphed vertices
    morphed_vertices = morph_vertices(
      current_vertices,
      target_vertices,
      morph_progress,
      state.morph_style,
      time
    )

    # Generate pixels for the frame
    pixels = render_polygon(
      state.width,
      state.height,
      morphed_vertices,
      {state.width / 2, state.height / 2},  # Center on LED grid
      state.scale,
      rotation_angle,
      state.fill_style,
      time,
      color_offset,
      state.color_scheme,
      state.brightness
    )

    # Create the frame
    frame = Frame.new("polygon_morph", state.width, state.height, pixels)

    # Update state
    new_state = %{state |
      time: time,
      morph_progress: morph_progress,
      current_vertices: current_vertices,
      target_vertices: target_vertices,
      current_vertex_count: current_vertex_count,
      target_vertex_count: target_vertex_count,
      rotation_angle: rotation_angle,
      color_offset: color_offset
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Get vertex count limits, ensuring min <= max
    vertex_count_min = PatternHelpers.get_param(params, "vertex_count_min", state.vertex_count_min, :integer)
    vertex_count_max = PatternHelpers.get_param(params, "vertex_count_max", state.vertex_count_max, :integer)
    vertex_count_min = min(vertex_count_min, vertex_count_max)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      morph_style: PatternHelpers.get_param(params, "morph_style", state.morph_style, :string),
      vertex_count_min: vertex_count_min,
      vertex_count_max: vertex_count_max,
      fill_style: PatternHelpers.get_param(params, "fill_style", state.fill_style, :string),
      rotation_enabled: PatternHelpers.get_param(params, "rotation_enabled", state.rotation_enabled, :boolean)
    }

    # Restart with new polygons if key parameters changed
    updated_state = if vertex_count_min != state.vertex_count_min ||
       vertex_count_max != state.vertex_count_max ||
       Map.get(params, "morph_style") != nil do
      initialize_polygons(updated_state)
    else
      updated_state
    end

    # Return the updated state with the correct tuple format
    {:ok, updated_state}
  end

  # Helper functions

  # Initialize starting and target polygons
  defp initialize_polygons(state) do
    current_vertex_count = select_random_vertex_count(state.vertex_count_min, state.vertex_count_max)
    target_vertex_count = select_next_vertex_count(current_vertex_count, state.vertex_count_min, state.vertex_count_max)

    current_vertices = generate_polygon(current_vertex_count, state.vertex_count_min, state.vertex_count_max)
    target_vertices = generate_polygon(target_vertex_count, state.vertex_count_min, state.vertex_count_max)

    %{state |
      current_vertices: current_vertices,
      target_vertices: target_vertices,
      current_vertex_count: current_vertex_count,
      target_vertex_count: target_vertex_count,
      morph_progress: 0.0
    }
  end

  # Select a random vertex count in range
  defp select_random_vertex_count(min, max) do
    min + :rand.uniform(max - min + 1) - 1
  end

  # Select next vertex count (different from current)
  defp select_next_vertex_count(current, min, max) do
    if max > min do
      # Select a different vertex count than current
      next = min + :rand.uniform(max - min + 1) - 1
      if next == current and (max - min) > 0 do
        # If we selected the same and have options, try again
        select_next_vertex_count(current, min, max)
      else
        next
      end
    else
      # If min == max, just return that value
      min
    end
  end

  # Generate a regular polygon with the given number of vertices
  defp generate_polygon(vertex_count, _min, _max) do
    # Generate equally spaced vertices around a circle
    for i <- 0..(vertex_count - 1) do
      angle = 2 * :math.pi * i / vertex_count

      # Radius variation for more interesting shapes
      radius = 1.0 + (:rand.uniform() - 0.5) * 0.1

      # Convert polar to cartesian coordinates (normalized)
      x = :math.cos(angle) * radius
      y = :math.sin(angle) * radius

      {x, y}
    end
  end

  # Morph between two sets of vertices
  defp morph_vertices(current, target, progress, style, time) do
    # Pad the shorter list to match lengths
    {padded_current, padded_target} = pad_vertices(current, target)

    # Apply easing function based on style
    eased_progress = case style do
      "smooth" -> smooth_ease(progress)
      "elastic" -> elastic_ease(progress)
      "bounce" -> bounce_ease(progress)
      "wave" -> wave_ease(progress, time)
      "spiral" -> progress  # Spiral is handled differently below
      _ -> progress         # Linear as fallback
    end

    # Interpolate between vertices
    Enum.zip(padded_current, padded_target)
    |> Enum.map(fn {{x1, y1}, {x2, y2}} ->
      case style do
        "spiral" ->
          # Spiral effect rotates vertices during morph
          angle = progress * :math.pi * 2
          # Interpolate distance
          r1 = :math.sqrt(x1 * x1 + y1 * y1)
          r2 = :math.sqrt(x2 * x2 + y2 * y2)
          r = r1 * (1 - progress) + r2 * progress

          # Get angle of each vertex and interpolate with additional spiral
          theta1 = :math.atan2(y1, x1)
          theta2 = :math.atan2(y2, x2)
          # Ensure shortest angle path
          theta2 = adjust_angle_for_shortest_path(theta1, theta2)
          theta = theta1 * (1 - progress) + theta2 * progress + angle * progress

          # Convert back to cartesian
          {r * :math.cos(theta), r * :math.sin(theta)}

        _ ->
          # Standard linear interpolation with easing
          {
            x1 * (1 - eased_progress) + x2 * eased_progress,
            y1 * (1 - eased_progress) + y2 * eased_progress
          }
      end
    end)
  end

  # Ensure angles take the shortest path for interpolation
  defp adjust_angle_for_shortest_path(a1, a2) do
    diff = PatternHelpers.rem_float(a2 - a1, 2 * :math.pi)
    if diff > :math.pi do
      a1 + diff - 2 * :math.pi
    else
      a1 + diff
    end
  end

  # Pad vertex lists to match length for morphing
  defp pad_vertices(current, target) do
    current_length = length(current)
    target_length = length(target)

    cond do
      current_length == target_length ->
        # Already equal length
        {current, target}

      current_length < target_length ->
        # Pad current with interpolated vertices
        padded_current = pad_vertex_list(current, target_length)
        {padded_current, target}

      current_length > target_length ->
        # Pad target with interpolated vertices
        padded_target = pad_vertex_list(target, current_length)
        {current, padded_target}
    end
  end

  # Pad a vertex list to the target length by interpolating between existing vertices
  defp pad_vertex_list(vertices, target_length) do
    original_length = length(vertices)

    if original_length >= target_length do
      Enum.take(vertices, target_length)
    else
      # We need to add vertices
      vertices_to_add = target_length - original_length

      # Create list of indices where to insert new vertices
      # We distribute them evenly
      insert_indices =
        0..(vertices_to_add - 1)
        |> Enum.map(fn i ->
          trunc(i * original_length / vertices_to_add)
        end)

      # Insert interpolated vertices
      {result, _} =
        Enum.reduce(insert_indices, {vertices, 0}, fn insert_idx, {acc, offset} ->
          adjusted_idx = insert_idx + offset

          # Get vertices to interpolate between
          v1 = Enum.at(vertices, rem(adjusted_idx, original_length))
          v2 = Enum.at(vertices, rem(adjusted_idx + 1, original_length))

          # Create interpolated vertex (halfway)
          {x1, y1} = v1
          {x2, y2} = v2
          new_vertex = {(x1 + x2) / 2, (y1 + y2) / 2}

          # Insert and return updated list and offset
          {List.insert_at(acc, adjusted_idx + 1, new_vertex), offset + 1}
        end)

      Enum.take(result, target_length)
    end
  end

  # Easing functions for smooth morphing

  defp smooth_ease(t) do
    # Cubic easing
    t * t * (3 - 2 * t)
  end

  defp elastic_ease(t) do
    # Elastic easing
    p = 0.3
    s = p / 4
    if t == 0 do
      0
    else
      if t == 1 do
        1
      else
        2 ** (-10 * t) * :math.sin((t - s) * (2 * :math.pi) / p) + 1
      end
    end
  end

  defp bounce_ease(t) do
    # Bounce easing
    if t < 1/2.75 do
      7.5625 * t * t
    else
      if t < 2/2.75 do
        t = t - 1.5/2.75
        7.5625 * t * t + 0.75
      else
        if t < 2.5/2.75 do
          t = t - 2.25/2.75
          7.5625 * t * t + 0.9375
        else
          t = t - 2.625/2.75
          7.5625 * t * t + 0.984375
        end
      end
    end
  end

  defp wave_ease(t, time) do
    # Wave easing adds a sine wave to the progress
    wave_amplitude = 0.1
    wave_frequency = 3.0
    base = t
    wave = :math.sin(t * :math.pi * wave_frequency + time * 2) * wave_amplitude * t * (1 - t)
    max(0, min(1, base + wave))
  end

  # Render the polygon to pixels
  defp render_polygon(width, height, vertices, center, scale, rotation, fill_style, time, color_offset, color_scheme, brightness) do
    {center_x, center_y} = center

    # Create an empty black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Calculate bounding box for iteration optimization
    {min_x, max_x, min_y, max_y} = calculate_bounding_box(vertices, center, scale, rotation)

    # Clamp to display bounds with padding
    min_x = max(0, trunc(min_x) - 1)
    max_x = min(width - 1, trunc(max_x) + 1)
    min_y = max(0, trunc(min_y) - 1)
    max_y = min(height - 1, trunc(max_y) + 1)

    # Rotate and scale vertices
    transformed_vertices = transform_vertices(vertices, center, scale, rotation)

    # Fill the polygon
    Enum.reduce(min_y..max_y, canvas, fn y, acc ->
      Enum.reduce(min_x..max_x, acc, fn x, inner_acc ->
        # Get normalized coordinates for pixel
        nx = (x - center_x) / (scale * width / 2)
        ny = (y - center_y) / (scale * height / 2)

        # Check if pixel is inside polygon
        if point_in_polygon?({nx, ny}, vertices) do
          # Calculate color based on fill style
          color = case fill_style do
            "solid" ->
              # Solid color based on polygon properties
              color_value = PatternHelpers.rem_float(color_offset, 1.0)
              PatternHelpers.get_color(color_scheme, color_value, brightness)

            "gradient" ->
              # Gradient based on position
              gradient_value = point_to_gradient_value({nx, ny}, vertices)
              color_value = PatternHelpers.rem_float(color_offset + gradient_value * 0.5, 1.0)
              PatternHelpers.get_color(color_scheme, color_value, brightness)

            "outline" ->
              # Only color near edges
              distance = distance_to_polygon_edge({nx, ny}, vertices)
              edge_threshold = 0.1
              if distance < edge_threshold do
                # Fade out as we move away from edge
                edge_brightness = (edge_threshold - distance) / edge_threshold * brightness
                color_value = PatternHelpers.rem_float(color_offset, 1.0)
                PatternHelpers.get_color(color_scheme, color_value, edge_brightness)
              else
                {0, 0, 0} # Black inside
              end

            "pulse" ->
              # Pulsing effect from center
              dist_from_center = :math.sqrt(nx * nx + ny * ny)
              pulse_value = :math.sin(dist_from_center * 5 - time * 3) * 0.5 + 0.5
              color_value = PatternHelpers.rem_float(color_offset + dist_from_center * 0.2, 1.0)
              pulse_brightness = pulse_value * brightness
              PatternHelpers.get_color(color_scheme, color_value, pulse_brightness)

            "radial" ->
              # Radial gradient from center
              dist_from_center = :math.sqrt(nx * nx + ny * ny)
              # Angle from center determines color
              angle = :math.atan2(ny, nx)
              angle_normalized = (angle + :math.pi) / (2 * :math.pi)
              # Distance determines brightness
              radial_brightness = (1.0 - dist_from_center) * brightness
              color_value = PatternHelpers.rem_float(color_offset + angle_normalized, 1.0)
              PatternHelpers.get_color(color_scheme, color_value, radial_brightness)

            _ ->
              # Default to solid
              color_value = PatternHelpers.rem_float(color_offset, 1.0)
              PatternHelpers.get_color(color_scheme, color_value, brightness)
          end

          # Update pixel in canvas
          idx = y * width + x
          List.replace_at(inner_acc, idx, color)
        else
          inner_acc
        end
      end)
    end)
  end

  # Transform vertices based on center, scale and rotation
  defp transform_vertices(vertices, {center_x, center_y}, scale, rotation) do
    # Apply rotation and scaling, then translate to center
    Enum.map(vertices, fn {x, y} ->
      # Rotate
      rotated_x = x * :math.cos(rotation) - y * :math.sin(rotation)
      rotated_y = x * :math.sin(rotation) + y * :math.cos(rotation)

      # Scale to appropriate size for the LED grid
      scaled_x = rotated_x * scale * (center_x * 0.8)
      scaled_y = rotated_y * scale * (center_y * 0.8)

      # Translate to center
      {center_x + scaled_x, center_y + scaled_y}
    end)
  end

  # Calculate bounding box for a set of vertices
  defp calculate_bounding_box(vertices, {center_x, center_y}, scale, rotation) do
    transformed = transform_vertices(vertices, {center_x, center_y}, scale, rotation)

    # Find mins and maxs
    {min_x, max_x, min_y, max_y} = Enum.reduce(transformed, {center_x, center_x, center_y, center_y},
      fn {x, y}, {min_x, max_x, min_y, max_y} ->
        {
          min(min_x, x),
          max(max_x, x),
          min(min_y, y),
          max(max_y, y)
        }
      end)

    {min_x, max_x, min_y, max_y}
  end

  # Determine if a point is inside a polygon using ray casting algorithm
  defp point_in_polygon?({px, py}, vertices) do
    vertex_count = length(vertices)

    Enum.reduce_while(0..(vertex_count - 1), false, fn i, inside ->
      j = rem(i + 1, vertex_count)

      {vi_x, vi_y} = Enum.at(vertices, i)
      {vj_x, vj_y} = Enum.at(vertices, j)

      intersect = ((vi_y > py) != (vj_y > py)) &&
                  (px < (vj_x - vi_x) * (py - vi_y) / (vj_y - vi_y) + vi_x)

      if intersect do
        {:cont, !inside}  # Flip inside/outside status
      else
        {:cont, inside}   # No change
      end
    end)
  end

  # Calculate gradient value based on position inside polygon
  defp point_to_gradient_value({px, py}, vertices) do
    # Use normalized distance from center as gradient value
    :math.sqrt(px * px + py * py)
  end

  # Calculate minimum distance from point to any polygon edge
  defp distance_to_polygon_edge({px, py}, vertices) do
    vertex_count = length(vertices)

    Enum.reduce(0..(vertex_count - 1), :infinity, fn i, min_dist ->
      j = rem(i + 1, vertex_count)

      {vi_x, vi_y} = Enum.at(vertices, i)
      {vj_x, vj_y} = Enum.at(vertices, j)

      # Calculate distance from point to line segment
      dist = point_to_line_distance({px, py}, {vi_x, vi_y}, {vj_x, vj_y})

      min(min_dist, dist)
    end)
  end

  # Calculate distance from a point to a line segment
  defp point_to_line_distance({px, py}, {x1, y1}, {x2, y2}) do
    # Length of line segment squared
    l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)

    if l2 == 0 do
      # Line segment is actually a point
      :math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1))
    else
      # Consider the line extending the segment, parameterized as x1 + t (x2 - x1)
      # Find projection of point p onto the line.
      # It falls where t = [(p-x1) . (x2-x1)] / |x2-x1|^2
      t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))

      # Projection falls on the segment if t in [0,1]
      projection_x = x1 + t * (x2 - x1)
      projection_y = y1 + t * (y2 - y1)

      :math.sqrt((px - projection_x) * (px - projection_x) + (py - projection_y) * (py - projection_y))
    end
  end
end
