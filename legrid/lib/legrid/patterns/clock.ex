defmodule Legrid.Patterns.Clock do
  @moduledoc """
  Pattern generator for a real-time clock display.

  Displays the current time in either digital or analog format on the LED grid.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  import Bitwise, only: [<<<: 2, >>>: 2, &&&: 2, |||: 2, ~~~: 1, ^^^: 2]

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  # Digital digit patterns (5x7 matrix for each digit)
  @digits %{
    0 => [
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    1 => [
      [0, 0, 1, 0, 0],
      [0, 1, 1, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 1, 1, 1, 0]
    ],
    2 => [
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 0],
      [1, 0, 0, 0, 0],
      [1, 1, 1, 1, 1]
    ],
    3 => [
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    4 => [
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1]
    ],
    5 => [
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 0],
      [1, 0, 0, 0, 0],
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    6 => [
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 0],
      [1, 0, 0, 0, 0],
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    7 => [
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 1, 0],
      [0, 0, 1, 0, 0],
      [0, 1, 0, 0, 0],
      [1, 0, 0, 0, 0]
    ],
    8 => [
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    9 => [
      [1, 1, 1, 1, 1],
      [1, 0, 0, 0, 1],
      [1, 0, 0, 0, 1],
      [1, 1, 1, 1, 1],
      [0, 0, 0, 0, 1],
      [0, 0, 0, 0, 1],
      [1, 1, 1, 1, 1]
    ],
    "colon" => [
      [0, 0, 0, 0, 0],
      [0, 0, 0, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 0, 0, 0],
      [0, 0, 1, 0, 0],
      [0, 0, 0, 0, 0],
      [0, 0, 0, 0, 0]
    ]
  }

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    %{
      id: "clock",
      name: "Clock",
      description: "Real-time clock display in various formats",
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
          default: "mono_blue",
          options: color_scheme_options,
          description: "Color scheme to use"
        },
        "speed" => %{
          type: :float,
          default: 1.0,
          min: 0.1,
          max: 2.0,
          description: "Animation speed (for seconds and effects)"
        },
        # Pattern-specific parameters
        "clock_type" => %{
          type: :enum,
          default: "digital",
          options: ["digital", "analog", "binary", "word"],
          description: "Type of clock display"
        },
        "show_seconds" => %{
          type: :boolean,
          default: true,
          description: "Whether to show seconds"
        },
        "use_24h" => %{
          type: :boolean,
          default: false,
          description: "Use 24-hour format (instead of 12-hour)"
        },
        "pulse_effect" => %{
          type: :boolean,
          default: true,
          description: "Add pulsing effect to the display"
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
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "mono_blue", :string),
      speed: PatternHelpers.get_param(params, "speed", 1.0, :float),
      # Pattern-specific parameters
      clock_type: PatternHelpers.get_param(params, "clock_type", "digital", :string),
      show_seconds: PatternHelpers.get_param(params, "show_seconds", true, :boolean),
      use_24h: PatternHelpers.get_param(params, "use_24h", false, :boolean),
      pulse_effect: PatternHelpers.get_param(params, "pulse_effect", true, :boolean),
      # Animation state
      time: 0.0,
      last_second: -1
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds with speed factor
    delta_time = elapsed_ms / 1000.0
    time = state.time + delta_time

    # Get current time
    now = :calendar.local_time()
    {{_year, _month, _day}, {hour, minute, second}} = now

    # Adjust hour for 12-hour format if needed
    hour = if !state.use_24h && hour > 12, do: hour - 12, else: hour
    hour = if !state.use_24h && hour == 0, do: 12, else: hour

    # Generate pixels based on clock type
    pixels = case state.clock_type do
      "digital" -> render_digital_clock(state.width, state.height, hour, minute, second, time, state)
      "analog" -> render_analog_clock(state.width, state.height, hour, minute, second, time, state)
      "binary" -> render_binary_clock(state.width, state.height, hour, minute, second, time, state)
      "word" -> render_word_clock(state.width, state.height, hour, minute, second, time, state)
      _ -> render_digital_clock(state.width, state.height, hour, minute, second, time, state)
    end

    # Create the frame
    frame = Frame.new("clock", state.width, state.height, pixels)

    # Update state with new time
    new_state = %{state | time: time, last_second: second}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      clock_type: PatternHelpers.get_param(params, "clock_type", state.clock_type, :string),
      show_seconds: PatternHelpers.get_param(params, "show_seconds", state.show_seconds, :boolean),
      use_24h: PatternHelpers.get_param(params, "use_24h", state.use_24h, :boolean),
      pulse_effect: PatternHelpers.get_param(params, "pulse_effect", state.pulse_effect, :boolean)
    }

    {:ok, updated_state}
  end

  # Helper functions for rendering different clock types

  # Digital clock: Renders time as digits
  defp render_digital_clock(width, height, hour, minute, second, time, state) do
    # Create black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Check if we should show seconds
    show_seconds = state.show_seconds

    # Calculate digit dimensions - 5 pixels wide, 7 tall
    digit_width = 5
    digit_height = 7

    # Calculate positions (centered on screen)
    if show_seconds do
      # Format: HH:MM:SS (8 elements with colons)
      total_width = digit_width * 8  # 2 digits for hour, 2 for minute, 2 for second, 2 colons
      start_x = div(width - total_width, 2)
      start_y = div(height - digit_height, 2)

      # Draw each digit
      canvas = draw_digit(canvas, width, div(hour, 10), start_x, start_y, time, state)
      canvas = draw_digit(canvas, width, rem(hour, 10), start_x + digit_width, start_y, time, state)
      canvas = draw_digit(canvas, width, "colon", start_x + digit_width * 2, start_y, time, state)
      canvas = draw_digit(canvas, width, div(minute, 10), start_x + digit_width * 3, start_y, time, state)
      canvas = draw_digit(canvas, width, rem(minute, 10), start_x + digit_width * 4, start_y, time, state)
      canvas = draw_digit(canvas, width, "colon", start_x + digit_width * 5, start_y, time, state)
      canvas = draw_digit(canvas, width, div(second, 10), start_x + digit_width * 6, start_y, time, state)
      canvas = draw_digit(canvas, width, rem(second, 10), start_x + digit_width * 7, start_y, time, state)
    else
      # Format: HH:MM (5 elements with one colon)
      total_width = digit_width * 5  # 2 digits for hour, 2 for minute, 1 colon
      start_x = div(width - total_width, 2)
      start_y = div(height - digit_height, 2)

      # Draw each digit
      canvas = draw_digit(canvas, width, div(hour, 10), start_x, start_y, time, state)
      canvas = draw_digit(canvas, width, rem(hour, 10), start_x + digit_width, start_y, time, state)
      canvas = draw_digit(canvas, width, "colon", start_x + digit_width * 2, start_y, time, state)
      canvas = draw_digit(canvas, width, div(minute, 10), start_x + digit_width * 3, start_y, time, state)
      canvas = draw_digit(canvas, width, rem(minute, 10), start_x + digit_width * 4, start_y, time, state)
    end

    canvas
  end

  # Analog clock: Renders time as a traditional clock face
  defp render_analog_clock(width, height, hour, minute, second, time, state) do
    center_x = div(width, 2)
    center_y = div(height, 2)
    radius = min(center_x, center_y) - 1

    # Create black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Draw clock face (circle outline)
    canvas = draw_circle(canvas, width, center_x, center_y, radius, time, state)

    # Calculate hand angles
    hour_angle = (:math.pi * 2 * (hour / 12 + minute / 60 / 12)) - :math.pi / 2
    minute_angle = (:math.pi * 2 * (minute / 60)) - :math.pi / 2
    second_angle = (:math.pi * 2 * (second / 60)) - :math.pi / 2

    # Draw hands
    # Hour hand (shorter)
    hour_length = trunc(radius * 0.5)
    hour_end_x = center_x + trunc(hour_length * :math.cos(hour_angle))
    hour_end_y = center_y + trunc(hour_length * :math.sin(hour_angle))
    canvas = draw_line(canvas, width, center_x, center_y, hour_end_x, hour_end_y, 0.8, time, state)

    # Minute hand (longer)
    minute_length = trunc(radius * 0.7)
    minute_end_x = center_x + trunc(minute_length * :math.cos(minute_angle))
    minute_end_y = center_y + trunc(minute_length * :math.sin(minute_angle))
    canvas = draw_line(canvas, width, center_x, center_y, minute_end_x, minute_end_y, 0.9, time, state)

    # Second hand (thinnest and red)
    if state.show_seconds do
      second_length = trunc(radius * 0.8)
      second_end_x = center_x + trunc(second_length * :math.cos(second_angle))
      second_end_y = center_y + trunc(second_length * :math.sin(second_angle))

      # Use a different color for second hand
      canvas = draw_line(canvas, width, center_x, center_y, second_end_x, second_end_y, 1.0, time,
                         %{state | color_scheme: "mono_red"})
    end

    # Draw center dot
    center_index = center_y * width + center_x
    color_value = 0.0
    brightness = state.brightness
    color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)
    List.replace_at(canvas, center_index, color)
  end

  # Binary clock: Renders time as binary LED patterns
  defp render_binary_clock(width, height, hour, minute, second, time, state) do
    # Create black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Set up binary grid dimensions
    rows = 6  # Hours (2 rows), minutes (2 rows), seconds (2 rows)
    cols = 4  # Binary representation: 8, 4, 2, 1

    # Calculate cell size and position
    cell_width = div(width, cols)
    cell_height = div(height, rows)

    # Convert time components to binary
    hour_tens = div(hour, 10)
    hour_ones = rem(hour, 10)
    minute_tens = div(minute, 10)
    minute_ones = rem(minute, 10)
    second_tens = div(second, 10)
    second_ones = rem(second, 10)

    # Draw binary representation for each time component
    canvas = draw_binary_component(canvas, width, hour_tens, 0, 0, cell_width, cell_height, time, state)
    canvas = draw_binary_component(canvas, width, hour_ones, 1, 0, cell_width, cell_height, time, state)
    canvas = draw_binary_component(canvas, width, minute_tens, 2, 0, cell_width, cell_height, time, state)
    canvas = draw_binary_component(canvas, width, minute_ones, 3, 0, cell_width, cell_height, time, state)

    if state.show_seconds do
      canvas = draw_binary_component(canvas, width, second_tens, 4, 0, cell_width, cell_height, time, state)
      canvas = draw_binary_component(canvas, width, second_ones, 5, 0, cell_width, cell_height, time, state)
    end

    canvas
  end

  # Word clock: Displays time as words (approximated)
  defp render_word_clock(width, height, hour, minute, second, time, state) do
    # Create black canvas
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # For word clock, we approximate time to nearest 5 minutes
    # and use a grid of letters that light up to display phrases like
    # "IT IS HALF PAST TEN"

    # This is a simplified version that just shows text at center
    # In a real implementation, we'd have a grid of letters with fixed positions

    # Determine the phrase to display
    minute_rounded = div(minute, 5) * 5
    phrase = get_time_phrase(hour, minute_rounded)

    # Draw the text centered (very simplified, just for demonstration)
    # In a real word clock, we'd highlight specific letters in a grid
    center_x = div(width, 2)
    center_y = div(height, 2)

    # Pulse brightness if enabled
    brightness = if state.pulse_effect do
      base = state.brightness * 0.7
      pulsing = (1.0 + :math.sin(time * state.speed)) / 2.0 * 0.3
      base + pulsing
    else
      state.brightness
    end

    # Set a color based on time
    color_value = hour / 24.0
    color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)

    # Just for demonstration, set the center pixel
    center_index = center_y * width + center_x
    List.replace_at(canvas, center_index, color)
  end

  # Helper functions for drawing

  # Draw a digit at the specified position
  defp draw_digit(canvas, width, digit, start_x, start_y, time, state) do
    # Get the digit pattern
    pattern = Map.get(@digits, digit)

    # Calculate pulse effect if enabled
    brightness = calculate_brightness(time, state)

    # Draw each pixel of the digit
    Enum.with_index(pattern)
    |> Enum.reduce(canvas, fn {row, y}, acc ->
      Enum.with_index(row)
      |> Enum.reduce(acc, fn {pixel, x}, inner_acc ->
        if pixel > 0 do
          # Calculate position on canvas
          pos_x = start_x + x
          pos_y = start_y + y

          # Only draw if within bounds
          if pos_x >= 0 && pos_x < width && pos_y >= 0 && pos_y < width do
            # Calculate index in flattened canvas
            index = pos_y * width + pos_x

            # Get color based on time
            color_value = (time * 0.05) + (x + y) * 0.01
            color_value = PatternHelpers.rem_float(color_value, 1.0)

            # Get color
            color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)

            # Update canvas
            List.replace_at(inner_acc, index, color)
          else
            inner_acc
          end
        else
          inner_acc
        end
      end)
    end)
  end

  # Draw a circle outline
  defp draw_circle(canvas, width, center_x, center_y, radius, time, state) do
    # Calculate pulse effect if enabled
    brightness = calculate_brightness(time, state) * 0.8  # Slightly dimmer for outline

    # Draw the circle outline using Bresenham's circle algorithm
    Enum.reduce(0..360, canvas, fn angle_deg, acc ->
      angle = angle_deg * :math.pi / 180
      x = center_x + trunc(radius * :math.cos(angle))
      y = center_y + trunc(radius * :math.sin(angle))

      # Only draw if within bounds
      if x >= 0 && x < width && y >= 0 && y < length(acc) / width do
        index = y * width + x

        # Vary color slightly based on angle
        color_value = PatternHelpers.rem_float(angle / (2 * :math.pi), 1.0)
        color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)

        List.replace_at(acc, index, color)
      else
        acc
      end
    end)
  end

  # Draw a line using Bresenham's algorithm
  defp draw_line(canvas, width, x0, y0, x1, y1, intensity, time, state) do
    # Calculate pulse effect if enabled
    brightness = calculate_brightness(time, state) * intensity

    # Bresenham's line algorithm
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = if x0 < x1, do: 1, else: -1
    sy = if y0 < y1, do: 1, else: -1
    err = dx + dy

    # Draw the line
    draw_line_point(canvas, width, x0, y0, x1, y1, dx, dy, sx, sy, err, brightness, time, state)
  end

  # Recursive implementation of Bresenham's line algorithm
  defp draw_line_point(canvas, width, x, y, x1, y1, dx, dy, sx, sy, err, brightness, time, state) do
    # Check if we're at the end point
    if x == x1 && y == y1 do
      # Set the end point
      if x >= 0 && x < width && y >= 0 && y < length(canvas) / width do
        index = y * width + x
        color_value = PatternHelpers.rem_float(time * 0.1, 1.0)
        color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)
        List.replace_at(canvas, index, color)
      else
        canvas
      end
    else
      # Set the current point
      canvas = if x >= 0 && x < width && y >= 0 && y < length(canvas) / width do
        index = y * width + x
        # Vary color slightly along the line
        progress = PatternHelpers.rem_float(((x - x1) * (x - x1) + (y - y1) * (y - y1)) * 0.01, 1.0)
        color_value = PatternHelpers.rem_float(time * 0.1 + progress, 1.0)
        color = PatternHelpers.get_color(state.color_scheme, color_value, brightness)
        List.replace_at(canvas, index, color)
      else
        canvas
      end

      # Calculate new error and position
      e2 = 2 * err
      {x, y, err} = cond do
        e2 >= dy ->
          {x + sx, y, err + dy}
        e2 <= dx ->
          {x, y + sy, err + dx}
        true ->
          {x + sx, y + sy, err + dx + dy}
      end

      # Continue drawing
      draw_line_point(canvas, width, x, y, x1, y1, dx, dy, sx, sy, err, brightness, time, state)
    end
  end

  # Draw a binary component (row of LEDs representing a digit in binary)
  defp draw_binary_component(canvas, width, value, row, col, cell_width, cell_height, time, state) do
    # Calculate pulse effect if enabled
    brightness = calculate_brightness(time, state)

    # Convert value to binary and draw each bit
    Enum.reduce(0..3, canvas, fn bit_position, acc ->
      # Calculate the bit value (8, 4, 2, 1)
      bit_value = 1 <<< (3 - bit_position)
      bit_on = (value &&& bit_value) > 0

      if bit_on do
        # Calculate position
        cell_x = col * cell_width + bit_position * cell_width + div(cell_width, 2)
        cell_y = row * cell_height + div(cell_height, 2)

        # Draw a filled circle to represent binary digit
        draw_filled_circle(acc, width, cell_x, cell_y, div(cell_width, 3), time, state, brightness)
      else
        acc
      end
    end)
  end

  # Draw a filled circle
  defp draw_filled_circle(canvas, width, center_x, center_y, radius, time, state, intensity) do
    # Draw each pixel in the circle
    Enum.reduce(-radius..radius, canvas, fn dy, acc ->
      Enum.reduce(-radius..radius, acc, fn dx, inner_acc ->
        # Check if point is within circle
        if dx * dx + dy * dy <= radius * radius do
          x = center_x + dx
          y = center_y + dy

          # Check bounds
          if x >= 0 && x < width && y >= 0 && y < length(canvas) / width do
            index = y * width + x

            # Calculate color with distance-based falloff
            dist_factor = 1.0 - (:math.sqrt(dx * dx + dy * dy) / radius)
            color_value = PatternHelpers.rem_float(time * 0.1, 1.0)
            color = PatternHelpers.get_color(state.color_scheme, color_value, intensity * dist_factor)

            List.replace_at(inner_acc, index, color)
          else
            inner_acc
          end
        else
          inner_acc
        end
      end)
    end)
  end

  # Calculate brightness with pulsing effect if enabled
  defp calculate_brightness(time, state) do
    if state.pulse_effect do
      # Calculate pulsing effect: base brightness plus a pulsing component
      base = state.brightness * 0.7
      pulsing = (1.0 + :math.sin(time * state.speed)) / 2.0 * 0.3
      base + pulsing
    else
      state.brightness
    end
  end

  # Get a phrase that represents the current time
  defp get_time_phrase(hour, minute) do
    # Very simple mapping
    cond do
      minute == 0 -> "#{hour} o'clock"
      minute == 30 -> "half past #{hour}"
      minute < 30 -> "#{minute} past #{hour}"
      true -> "#{60 - minute} to #{hour + 1}"
    end
  end
end
