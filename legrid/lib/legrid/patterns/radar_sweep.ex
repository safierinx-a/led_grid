defmodule Legrid.Patterns.RadarSweep do
  @moduledoc """
  Pattern generator for a radar sweep visualization.

  Displays a radar screen with a sweeping beam and randomly positioned "detected" objects.
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
      id: "radar_sweep",
      name: "Radar Sweep",
      description: "Radar screen with sweeping beam and object detection",
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
          default: "mono_green",
          options: color_scheme_options,
          description: "Color scheme to use"
        },
        "speed" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 2.0,
          description: "Sweep speed"
        },
        # Pattern-specific parameters
        "object_count" => %{
          type: :integer,
          default: 5,
          min: 0,
          max: 20,
          description: "Number of objects to detect"
        },
        "object_size" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 1.0,
          description: "Size of detected objects"
        },
        "trail_length" => %{
          type: :float,
          default: 0.3,
          min: 0.0,
          max: 1.0,
          description: "Length of sweep trail"
        },
        "noise_level" => %{
          type: :float,
          default: 0.05,
          min: 0.0,
          max: 0.5,
          description: "Background noise level"
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
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "mono_green", :string),
      speed: PatternHelpers.get_param(params, "speed", 0.5, :float),
      # Pattern-specific parameters
      object_count: PatternHelpers.get_param(params, "object_count", 5, :integer),
      object_size: PatternHelpers.get_param(params, "object_size", 0.5, :float),
      trail_length: PatternHelpers.get_param(params, "trail_length", 0.3, :float),
      noise_level: PatternHelpers.get_param(params, "noise_level", 0.05, :float),
      # Animation state
      time: 0.0,
      sweep_angle: 0.0,
      objects: generate_objects(@default_width, @default_height, PatternHelpers.get_param(params, "object_count", 5, :integer)),
      detection_history: %{}
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds with speed factor
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update sweep angle - let it increase continuously without wrapping
    sweep_angle = state.sweep_angle + delta_time

    # Calculate trail angle
    trail_angle = sweep_angle - state.trail_length * 2 * :math.pi

    detection_history =
      state.objects
      |> Enum.reduce(state.detection_history, fn object, acc ->
        # Calculate angle to object from center
        object_angle = :math.atan2(object.y - state.height / 2, object.x - state.width / 2)

        # Check if the sweep beam is currently over this object
        is_detected = in_sweep_range?(object_angle, sweep_angle, trail_angle)

        # Get previous detected state or default to false
        was_detected = Map.get(acc, object.id, %{})
                       |> Map.get(:detected, false)

        # If newly detected or already detected, update detection info
        if is_detected do
          # Calculate "signal strength" based on distance from center
          center_x = state.width / 2
          center_y = state.height / 2
          distance = :math.sqrt(:math.pow(object.x - center_x, 2) + :math.pow(object.y - center_y, 2))
          max_distance = :math.sqrt(:math.pow(state.width / 2, 2) + :math.pow(state.height / 2, 2))
          signal_strength = 1.0 - (distance / max_distance) * 0.7  # Scale to keep minimum brightness

          # Update detection history for this object
          Map.put(acc, object.id, %{
            detected: true,
            last_detection: time,
            signal_strength: signal_strength
          })
        else
          # If it was previously detected but now isn't, keep it in history with updated time
          if was_detected do
            # Get last detection time
            last_detection = Map.get(acc, object.id, %{})
                             |> Map.get(:last_detection, 0)

            # Fade time determines how long the object remains visible after detection
            fade_time = 1.0 + state.object_size * 3.0  # Larger objects remain visible longer

            if time - last_detection < fade_time do
              # Calculate fade factor based on time since detection
              fade_factor = 1.0 - (time - last_detection) / fade_time

              # Update with fading signal strength
              signal_strength = Map.get(acc, object.id, %{})
                                |> Map.get(:signal_strength, 1.0)

              Map.put(acc, object.id, %{
                detected: false,
                last_detection: last_detection,
                signal_strength: signal_strength * fade_factor
              })
            else
              # Object has faded completely
              Map.put(acc, object.id, %{detected: false})
            end
          else
            # Still not detected
            Map.put(acc, object.id, %{detected: false})
          end
        end
      end)

    # Generate pixels for the frame
    pixels = render_radar(state.width, state.height, sweep_angle, trail_angle, state.objects,
                          detection_history, time, state)

    # Create the frame
    frame = Frame.new("radar_sweep", state.width, state.height, pixels)

    # Update state
    new_state = %{state |
      time: time,
      sweep_angle: sweep_angle,
      detection_history: detection_history
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Check if we need to regenerate objects
    regenerate_objects = Map.has_key?(params, "object_count")

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      object_count: PatternHelpers.get_param(params, "object_count", state.object_count, :integer),
      object_size: PatternHelpers.get_param(params, "object_size", state.object_size, :float),
      trail_length: PatternHelpers.get_param(params, "trail_length", state.trail_length, :float),
      noise_level: PatternHelpers.get_param(params, "noise_level", state.noise_level, :float)
    }

    # Regenerate objects if needed
    updated_state = if regenerate_objects do
      %{updated_state |
        objects: generate_objects(state.width, state.height, updated_state.object_count),
        detection_history: %{}  # Reset history since objects are new
      }
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Generate random objects positioned around the radar screen
  defp generate_objects(width, height, count) do
    center_x = width / 2
    center_y = height / 2

    for i <- 1..count do
      # Generate random position (polar coordinates to distribute evenly)
      angle = :rand.uniform() * 2 * :math.pi
      # Random distance from center, but not too close
      distance = (:rand.uniform() * 0.8 + 0.2) * min(center_x, center_y)

      # Convert to Cartesian coordinates
      x = center_x + distance * :math.cos(angle)
      y = center_y + distance * :math.sin(angle)

      # Random size factor for the object
      size_factor = :rand.uniform() * 0.5 + 0.5

      # Create object with unique id
      %{
        id: i,
        x: x,
        y: y,
        size_factor: size_factor
      }
    end
  end

  # Render the radar visualization using spatial operations
  defp render_radar(width, height, sweep_angle, trail_angle, objects, detection_history, time, state) do
    frame = %Frame{width: width, height: height, pixels: []}
    center = {width / 2, height / 2}

    # Generate angle field for sweep detection
    angle_field = SpatialHelpers.angle_field(frame, center)

    # Generate distance field for grid and object detection
    distance_field = SpatialHelpers.distance_field(frame, center)

    # Create sweep mask
    sweep_mask = SpatialHelpers.apply_function(angle_field, fn angle ->
      if in_sweep_range?(angle, sweep_angle, trail_angle) do
        # Calculate brightness based on distance from sweep line
        # Use modulo to find the closest sweep position
        current_sweep = PatternHelpers.rem_float(sweep_angle, 2 * :math.pi)
        angle_diff = min(
          min(abs(angle - current_sweep), abs(angle - current_sweep + 2 * :math.pi)),
          abs(angle - current_sweep - 2 * :math.pi)
        )
        max(0.0, 1.0 - (angle_diff / (state.trail_length * 2 * :math.pi)))
      else
        0.0
      end
    end)

    # Create grid mask using distance field
    max_radius = SpatialHelpers.max_dimension(frame) / 2
    grid_mask = SpatialHelpers.apply_function(distance_field, fn distance ->
      # Concentric circles
      ring_1 = if abs(distance - max_radius * 0.3) < 0.5, do: 0.3, else: 0.0
      ring_2 = if abs(distance - max_radius * 0.6) < 0.5, do: 0.3, else: 0.0
      ring_3 = if abs(distance - max_radius * 0.9) < 0.5, do: 0.3, else: 0.0
      max(ring_1, max(ring_2, ring_3))
    end)

    # Add radial grid lines using angle field
    radial_mask = SpatialHelpers.combine_fields([angle_field, distance_field], fn angle_field, distance_field ->
      Enum.zip(angle_field, distance_field)
      |> Enum.map(fn {angle, distance} ->
        # Create radial lines every 45 degrees
        line_strength = Enum.reduce(0..7, 0.0, fn i, acc ->
          target_angle = i * :math.pi / 4
          angle_diff = abs(PatternHelpers.rem_float(angle - target_angle, 2 * :math.pi))
          line_strength = if angle_diff < 0.1 || angle_diff > 2 * :math.pi - 0.1 do
            0.3
          else
            0.0
          end
          max(acc, line_strength)
        end)

        # Only show radial lines within radar range
        if distance < max_radius * 0.9, do: line_strength, else: 0.0
      end)
    end)

    # Combine all masks and convert to pixels
    SpatialHelpers.spatial_to_frame(frame, [distance_field, angle_field, sweep_mask, grid_mask, radial_mask],
      fn [distance, angle, sweep, grid, radial], x, y ->
        max_radius = SpatialHelpers.max_dimension(frame) / 2
        norm_distance = distance / max_radius

        cond do
          # Draw detected objects
          is_detected_object?(x, y, objects, detection_history, state.object_size) ->
            {object_id, signal_strength} = get_object_at(x, y, objects, detection_history, state.object_size)
            pulse = (1.0 + :math.sin(time * 4.0 + object_id)) / 2.0 * 0.3 + 0.7
            brightness = signal_strength * pulse * state.brightness
            PatternHelpers.get_color(state.color_scheme, 0.8, brightness)

          # Draw sweep beam
          sweep > 0.1 ->
            brightness = sweep * state.brightness
            PatternHelpers.get_color(state.color_scheme, 0.2, brightness)

          # Draw grid (combine concentric and radial)
          max(grid, radial) > 0.1 ->
            brightness = max(grid, radial) * state.brightness
            PatternHelpers.get_color(state.color_scheme, 0.0, brightness)

          # Background noise
          :rand.uniform() < state.noise_level ->
            noise_level = :rand.uniform() * 0.2 * state.brightness
            PatternHelpers.get_color(state.color_scheme, 0.0, noise_level)

          # Default background with distance fade
          true ->
            background = 0.05 * (1.0 - norm_distance * 0.7) * state.brightness
            PatternHelpers.get_color(state.color_scheme, 0.0, background)
        end
      end)
  end

  # Helper function to check if a point is on a grid line
  defp is_grid_line?(x, y, center_x, center_y, max_radius) do
    dx = x - center_x
    dy = y - center_y
    distance = :math.sqrt(dx * dx + dy * dy)

    # Draw 3 concentric circles and radial lines
    circle_1 = abs(distance - max_radius * 0.3) < 0.5
    circle_2 = abs(distance - max_radius * 0.6) < 0.5
    circle_3 = abs(distance - max_radius * 0.9) < 0.5

    # Radial lines every 45 degrees
    angle = :math.atan2(dy, dx)
    radial_line =
      Enum.any?(0..7, fn i ->
        target_angle = i * :math.pi / 4
        diff = abs(rem_float(angle - target_angle, 2 * :math.pi))
        diff < 0.1 || diff > 2 * :math.pi - 0.1
      end)

    circle_1 || circle_2 || circle_3 || (radial_line && distance < max_radius * 0.9)
  end

  # Helper function to check if an angle is within the current sweep range
  defp in_sweep_range?(angle, sweep_angle, trail_angle) do
    SpatialHelpers.angle_in_sweep?(angle, sweep_angle, trail_angle)
  end

  # Helper function to check if a point is part of a detected object
  defp is_detected_object?(x, y, objects, detection_history, object_size_param) do
    Enum.any?(objects, fn object ->
      # Calculate distance from point to object center
      dx = x - object.x
      dy = y - object.y
      distance = :math.sqrt(dx * dx + dy * dy)

      # Calculate object radius based on size parameter and object's size factor
      radius = 0.5 + object_size_param * object.size_factor

      # Check if point is within object radius
      if distance <= radius do
        # Check if object is detected (or recently detected)
        detection_info = Map.get(detection_history, object.id, %{detected: false})
        detection_info.detected || Map.get(detection_info, :signal_strength, 0) > 0.1
      else
        false
      end
    end)
  end

  # Helper function to get object ID and signal strength at a specific point
  defp get_object_at(x, y, objects, detection_history, object_size_param) do
    # Find the object at this position
    object = Enum.find(objects, fn object ->
      # Calculate distance from point to object center
      dx = x - object.x
      dy = y - object.y
      distance = :math.sqrt(dx * dx + dy * dy)

      # Calculate object radius based on size parameter and object's size factor
      radius = 0.5 + object_size_param * object.size_factor

      # Check if point is within object radius
      distance <= radius
    end)

    if object do
      # Get detection info
      detection_info = Map.get(detection_history, object.id, %{detected: false})
      signal_strength = Map.get(detection_info, :signal_strength, 0.2)

      {object.id, signal_strength}
    else
      {0, 0.0}
    end
  end

  # Helper for floating point remainder that handles negative values correctly
  defp rem_float(a, b) do
    PatternHelpers.rem_float(a, b)
  end
end
