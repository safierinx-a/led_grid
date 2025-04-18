defmodule Legrid.Patterns.TheatreText do
  @moduledoc """
  Pattern generator for theatre-style text displays.

  Creates marquee and static theatre-style text with various animation effects.
  Includes presets for classic messages and supports custom text input.
  """

  @behaviour Legrid.Patterns.PatternBehaviour

  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  # Font data - 3x5 dot matrix characters
  # Each character is defined in a 3x5 grid with 1 for lit pixel, 0 for off
  @font %{
    "A" => [
      [0, 1, 0],
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "B" => [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0]
    ],
    "C" => [
      [0, 1, 1],
      [1, 0, 0],
      [1, 0, 0],
      [1, 0, 0],
      [0, 1, 1]
    ],
    "D" => [
      [1, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 0]
    ],
    "E" => [
      [1, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [1, 0, 0],
      [1, 1, 1]
    ],
    "F" => [
      [1, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [1, 0, 0],
      [1, 0, 0]
    ],
    "G" => [
      [0, 1, 1],
      [1, 0, 0],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 1]
    ],
    "H" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "I" => [
      [1, 1, 1],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
      [1, 1, 1]
    ],
    "J" => [
      [0, 0, 1],
      [0, 0, 1],
      [0, 0, 1],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "K" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "L" => [
      [1, 0, 0],
      [1, 0, 0],
      [1, 0, 0],
      [1, 0, 0],
      [1, 1, 1]
    ],
    "M" => [
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "N" => [
      [1, 0, 1],
      [1, 1, 1],
      [1, 1, 1],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "O" => [
      [0, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "P" => [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 0],
      [1, 0, 0]
    ],
    "Q" => [
      [0, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 1]
    ],
    "R" => [
      [1, 1, 0],
      [1, 0, 1],
      [1, 1, 0],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "S" => [
      [0, 1, 1],
      [1, 0, 0],
      [0, 1, 0],
      [0, 0, 1],
      [1, 1, 0]
    ],
    "T" => [
      [1, 1, 1],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0]
    ],
    "U" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "V" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0],
      [0, 1, 0]
    ],
    "W" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 1],
      [1, 0, 1]
    ],
    "X" => [
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0],
      [1, 0, 1],
      [1, 0, 1]
    ],
    "Y" => [
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0]
    ],
    "Z" => [
      [1, 1, 1],
      [0, 0, 1],
      [0, 1, 0],
      [1, 0, 0],
      [1, 1, 1]
    ],
    "0" => [
      [0, 1, 0],
      [1, 0, 1],
      [1, 0, 1],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "1" => [
      [0, 1, 0],
      [1, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
      [1, 1, 1]
    ],
    "2" => [
      [1, 1, 0],
      [0, 0, 1],
      [0, 1, 0],
      [1, 0, 0],
      [1, 1, 1]
    ],
    "3" => [
      [1, 1, 0],
      [0, 0, 1],
      [0, 1, 0],
      [0, 0, 1],
      [1, 1, 0]
    ],
    "4" => [
      [1, 0, 1],
      [1, 0, 1],
      [1, 1, 1],
      [0, 0, 1],
      [0, 0, 1]
    ],
    "5" => [
      [1, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [0, 0, 1],
      [1, 1, 0]
    ],
    "6" => [
      [0, 1, 1],
      [1, 0, 0],
      [1, 1, 0],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "7" => [
      [1, 1, 1],
      [0, 0, 1],
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0]
    ],
    "8" => [
      [0, 1, 0],
      [1, 0, 1],
      [0, 1, 0],
      [1, 0, 1],
      [0, 1, 0]
    ],
    "9" => [
      [0, 1, 0],
      [1, 0, 1],
      [0, 1, 1],
      [0, 0, 1],
      [0, 1, 0]
    ],
    " " => [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0]
    ],
    "!" => [
      [0, 1, 0],
      [0, 1, 0],
      [0, 1, 0],
      [0, 0, 0],
      [0, 1, 0]
    ],
    "?" => [
      [0, 1, 0],
      [1, 0, 1],
      [0, 0, 1],
      [0, 1, 0],
      [0, 0, 0]
    ],
    "." => [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 1, 0]
    ],
    "," => [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
      [0, 1, 0],
      [1, 0, 0]
    ],
    "-" => [
      [0, 0, 0],
      [0, 0, 0],
      [1, 1, 1],
      [0, 0, 0],
      [0, 0, 0]
    ]
  }

  # Text presets for quick selection
  @presets %{
    "exit" => "EXIT",
    "no_way_out" => "NO WAY OUT",
    "danger" => "DANGER",
    "help" => "HELP",
    "closed" => "CLOSED",
    "emergency" => "EMERGENCY",
    "run" => "RUN",
    "dont_panic" => "DON'T PANIC",
    "out_of_order" => "OUT OF ORDER",
    "keep_out" => "KEEP OUT",
    "warning" => "WARNING",
    "beware" => "BEWARE",
    "private" => "PRIVATE",
    "stay_away" => "STAY AWAY",
    "welcome" => "WELCOME",
    "look_up" => "LOOK UP",
    "you_are_here" => "YOU ARE HERE",
    "watch_your_step" => "WATCH YOUR STEP"
  }

  @impl true
  def metadata do
    # Get all available color schemes
    color_schemes = PatternHelpers.color_schemes()
    color_scheme_options = Map.keys(color_schemes)

    # Get all available presets
    preset_options = Map.keys(@presets)

    %{
      id: "theatre_text",
      name: "Theatre Text",
      description: "Theatre-style marquee text display with presets and custom text",
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
          default: "mono_red",
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
        "text" => %{
          type: :string,
          default: "EXIT",
          description: "Custom text to display"
        },
        "preset" => %{
          type: :enum,
          default: "exit",
          options: preset_options,
          description: "Preset text message"
        },
        "use_preset" => %{
          type: :boolean,
          default: true,
          description: "Use preset text instead of custom text"
        },
        "mode" => %{
          type: :enum,
          default: "static",
          options: ["static", "blink", "scroll", "pulse"],
          description: "Text display mode"
        },
        "spacing" => %{
          type: :integer,
          default: 1,
          min: 1,
          max: 3,
          description: "Spacing between characters"
        },
        "scale" => %{
          type: :integer,
          default: 1,
          min: 1,
          max: 2,
          description: "Character scaling"
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
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "mono_red", :string),
      speed: PatternHelpers.get_param(params, "speed", 0.5, :float),
      # Pattern-specific parameters
      text: PatternHelpers.get_param(params, "text", "EXIT", :string),
      preset: PatternHelpers.get_param(params, "preset", "exit", :string),
      use_preset: PatternHelpers.get_param(params, "use_preset", true, :boolean),
      mode: PatternHelpers.get_param(params, "mode", "static", :string),
      spacing: PatternHelpers.get_param(params, "spacing", 1, :integer),
      scale: PatternHelpers.get_param(params, "scale", 1, :integer),
      # Animation state
      time: 0.0,
      scroll_offset: 0,
      blink_state: true,
      pulse_value: 0.0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update animation state
    delta_time = elapsed_ms / 1000.0

    # Choose text to display (either preset or custom)
    display_text = if state.use_preset do
      Map.get(@presets, state.preset, "EXIT")
    else
      state.text |> String.upcase()
    end

    # Update animation state based on mode
    {new_time, new_scroll_offset, new_blink_state, new_pulse_value} = update_animation_state(
      state.mode,
      state.time,
      state.scroll_offset,
      state.blink_state,
      state.pulse_value,
      delta_time,
      state.speed,
      display_text,
      state.width,
      state.scale,
      state.spacing
    )

    # Visibility based on animation mode
    {visible, brightness_multiplier} = determine_visibility(
      state.mode,
      new_blink_state,
      new_pulse_value
    )

    # Generate pixels for the frame
    pixels = if visible do
      brightness = state.brightness * brightness_multiplier
      render_text(
        display_text,
        state.width,
        state.height,
        new_scroll_offset,
        state.scale,
        state.spacing,
        state.color_scheme,
        brightness
      )
    else
      # Empty frame (all pixels off)
      for _y <- 0..(state.height - 1), _x <- 0..(state.width - 1), do: {0, 0, 0}
    end

    # Create the frame
    frame = Frame.new("theatre_text", state.width, state.height, pixels)

    # Update state with new animation values
    new_state = %{state |
      time: new_time,
      scroll_offset: new_scroll_offset,
      blink_state: new_blink_state,
      pulse_value: new_pulse_value
    }

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Start with global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      text: PatternHelpers.get_param(params, "text", state.text, :string),
      preset: PatternHelpers.get_param(params, "preset", state.preset, :string),
      use_preset: PatternHelpers.get_param(params, "use_preset", state.use_preset, :boolean),
      mode: PatternHelpers.get_param(params, "mode", state.mode, :string),
      spacing: PatternHelpers.get_param(params, "spacing", state.spacing, :integer),
      scale: PatternHelpers.get_param(params, "scale", state.scale, :integer)
    }

    {:ok, updated_state}
  end

  # Helper function to update animation state based on mode
  defp update_animation_state(mode, time, scroll_offset, blink_state, pulse_value, delta_time, speed, text, width, scale, spacing) do
    case mode do
      "static" ->
        # Static mode doesn't animate
        {time, 0, true, 0.0}

      "blink" ->
        # Update blink state approximately twice per second
        new_time = time + (delta_time * speed)
        new_blink_state = rem(trunc(new_time * 2), 2) == 0
        {new_time, 0, new_blink_state, 0.0}

      "scroll" ->
        # Calculate total text width in pixels
        text_width = calculate_text_width(text, scale, spacing)
        padding = width  # Add padding equal to screen width

        # Update scroll position
        new_time = time + (delta_time * speed)
        speed_factor = 8.0 * speed  # Pixels per second

        # Calculate new offset, wrapping around when text exits screen
        new_offset = -trunc(new_time * speed_factor)
        effective_offset = rem(new_offset, text_width + padding)

        {new_time, effective_offset, true, 0.0}

      "pulse" ->
        # Pulsating brightness
        new_time = time + (delta_time * speed)
        # Sine wave for smooth pulsation between 0.3 and 1.0
        new_pulse_value = 0.35 + 0.65 * ((:math.sin(new_time * 4 * speed) + 1) / 2)
        {new_time, 0, true, new_pulse_value}

      _ ->
        # Default fallback
        {time, scroll_offset, blink_state, pulse_value}
    end
  end

  # Helper function to determine visibility based on animation mode
  defp determine_visibility(mode, blink_state, pulse_value) do
    case mode do
      "blink" -> {blink_state, 1.0}
      "pulse" -> {true, pulse_value}
      _ -> {true, 1.0}
    end
  end

  # Helper function to render text on the grid
  defp render_text(text, width, height, scroll_offset, scale, char_spacing, color_scheme, brightness) do
    # Get characters from text
    chars = String.graphemes(text)

    # Create a grid of all pixels (initially off)
    grid = for y <- 0..(height - 1), x <- 0..(width - 1), do: {{x, y}, {0, 0, 0}}
    grid = Map.new(grid)

    # Determine vertical centering
    char_height = 5 * scale
    vertical_offset = div(height - char_height, 2)

    # Render each character at its position
    {grid, _} = Enum.reduce(chars, {grid, scroll_offset}, fn char, {current_grid, x_offset} ->
      # Skip if character is not visible on screen
      if x_offset > width or (x_offset + (3 * scale)) < 0 do
        # Character is completely off screen, just advance position
        {current_grid, x_offset + (3 * scale) + char_spacing}
      else
        # Get the character matrix, defaulting to space if not found
        char_matrix = Map.get(@font, char, @font[" "])

        # Draw this character
        new_grid = draw_character(current_grid, char_matrix, x_offset, vertical_offset, scale, color_scheme, brightness)

        # Return updated grid and x position
        {new_grid, x_offset + (3 * scale) + char_spacing}
      end
    end)

    # Convert grid map back to pixel list
    for y <- 0..(height - 1), x <- 0..(width - 1) do
      Map.get(grid, {x, y}, {0, 0, 0})
    end
  end

  # Helper function to draw a character onto the grid
  defp draw_character(grid, char_matrix, x_offset, y_offset, scale, color_scheme, brightness) do
    # Go through each position in the character matrix
    Enum.reduce(0..4, grid, fn y, current_grid ->
      Enum.reduce(0..2, current_grid, fn x, row_grid ->
        # Get the pixel state (0 or 1)
        pixel_on = case Enum.at(char_matrix, y) do
          nil -> 0
          row -> Enum.at(row, x, 0)
        end

        if pixel_on == 1 do
          # Draw the pixel (scaled)
          draw_scaled_pixel(row_grid, x_offset + (x * scale), y_offset + (y * scale), scale, color_scheme, brightness)
        else
          # Pixel is off, don't change the grid
          row_grid
        end
      end)
    end)
  end

  # Helper function to draw a scaled pixel onto the grid
  defp draw_scaled_pixel(grid, x, y, scale, color_scheme, brightness) do
    # Color value based on position (constant for static display)
    color_value = 0.8

    # Get color based on scheme
    color = PatternHelpers.get_color(color_scheme, color_value, brightness)

    # Apply the pixel at each position in the scale
    Enum.reduce(0..(scale-1), grid, fn y_offset, y_grid ->
      Enum.reduce(0..(scale-1), y_grid, fn x_offset, current_grid ->
        pos_x = x + x_offset
        pos_y = y + y_offset

        # Only draw if within bounds
        if pos_x >= 0 and pos_x < @default_width and pos_y >= 0 and pos_y < @default_height do
          Map.put(current_grid, {pos_x, pos_y}, color)
        else
          current_grid
        end
      end)
    end)
  end

  # Helper function to calculate total width of text in pixels
  defp calculate_text_width(text, scale, spacing) do
    char_count = String.length(text)
    (char_count * 3 * scale) + ((char_count - 1) * spacing)
  end
end
