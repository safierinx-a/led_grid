defmodule Legrid.Patterns.ComplexPixelArt do
  @moduledoc """
  Pattern generator for more complex pixel art with different sized units.

  Supports 8x8, 12x12, and 24x24 pixel art that fits into the LED grid.
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
      id: "complex_pixel_art",
      name: "Complex Pixel Art",
      description: "More complex pixel art with 8x8, 12x12, and 24x24 unit sizes",
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
        "art_size" => %{
          type: :enum,
          default: "8x8",
          options: ["8x8", "12x12", "24x24"],
          description: "Size of the pixel art units"
        },
        "art_type" => %{
          type: :enum,
          default: "retro",
          options: ["retro", "game", "abstract", "emoji"],
          description: "Type of pixel art to display"
        },
        "display_mode" => %{
          type: :enum,
          default: "single",
          options: ["single", "tiled", "scrolling"],
          description: "How to display the artwork on the grid"
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
      art_size: PatternHelpers.get_param(params, "art_size", "8x8", :string),
      art_type: PatternHelpers.get_param(params, "art_type", "retro", :string),
      display_mode: PatternHelpers.get_param(params, "display_mode", "single", :string),
      # Animation state
      time: 0.0,
      current_art: nil,
      art_position: {0, 0},
      scroll_offset: 0
    }

    # Initialize the current art based on size and type
    state = %{state | current_art: select_pixel_art(state.art_size, state.art_type)}

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update scroll offset for scrolling mode
    scroll_offset = case state.display_mode do
      "scrolling" -> rem(trunc(time * 5), state.width * 2)
      _ -> state.scroll_offset
    end

    # Generate frame pixels based on the current art and display mode
    pixels = case state.display_mode do
      "single" -> render_single(state.current_art, state.width, state.height, state.color_scheme, state.brightness, time)
      "tiled" -> render_tiled(state.current_art, state.width, state.height, state.color_scheme, state.brightness, time)
      "scrolling" -> render_scrolling(state.current_art, state.width, state.height, scroll_offset, state.color_scheme, state.brightness, time)
      _ -> render_single(state.current_art, state.width, state.height, state.color_scheme, state.brightness, time) # Default to single
    end

    # Create the frame
    frame = Frame.new("complex_pixel_art", state.width, state.height, pixels)

    # Update state
    new_state = %{state | time: time, scroll_offset: scroll_offset}

    {:ok, frame, new_state}
  end

  # Render a single centered pixel art on the grid
  defp render_single(art, grid_width, grid_height, color_scheme, brightness, time) do
    # Calculate center position to place the art
    start_x = div(grid_width - art.width, 2)
    start_y = div(grid_height - art.height, 2)

    # Create an empty canvas
    canvas = for _y <- 0..(grid_height-1), _x <- 0..(grid_width-1), do: {0, 0, 0}

    # Render the art onto the canvas
    render_art_to_canvas(canvas, art, start_x, start_y, grid_width, grid_height, color_scheme, brightness, time)
  end

  # Render pixel art tiled across the grid
  defp render_tiled(art, grid_width, grid_height, color_scheme, brightness, time) do
    # Create an empty canvas
    canvas = for _y <- 0..(grid_height-1), _x <- 0..(grid_width-1), do: {0, 0, 0}

    # Calculate how many times we can tile horizontally and vertically
    tiles_x = ceil(grid_width / art.width) + 1
    tiles_y = ceil(grid_height / art.height) + 1

    # Render each tile
    Enum.reduce(0..(tiles_y-1), canvas, fn y, canvas_acc ->
      Enum.reduce(0..(tiles_x-1), canvas_acc, fn x, inner_acc ->
        start_x = x * art.width
        start_y = y * art.height
        render_art_to_canvas(inner_acc, art, start_x, start_y, grid_width, grid_height, color_scheme, brightness, time + x * 0.1 + y * 0.1)
      end)
    end)
  end

  # Render pixel art scrolling across the grid
  defp render_scrolling(art, grid_width, grid_height, scroll_offset, color_scheme, brightness, time) do
    # Create an empty canvas
    canvas = for _y <- 0..(grid_height-1), _x <- 0..(grid_width-1), do: {0, 0, 0}

    # Calculate start positions with scrolling offset
    start_x = -scroll_offset

    # Render multiple copies of the art to ensure continuous scrolling
    copies = ceil(grid_width / art.width) * 2 + 1

    Enum.reduce(0..(copies-1), canvas, fn i, acc ->
      pos_x = start_x + (i * art.width)
      # Center vertically
      pos_y = div(grid_height - art.height, 2)
      render_art_to_canvas(acc, art, pos_x, pos_y, grid_width, grid_height, color_scheme, brightness, time + i * 0.1)
    end)
  end

  # Helper function to render art to a canvas at specific position
  defp render_art_to_canvas(canvas, art, start_x, start_y, grid_width, grid_height, color_scheme, brightness, time) do
    # Extract art pixels
    art_pixels = art.pixels

    # For each pixel in the art
    Enum.with_index(art_pixels)
    |> Enum.reduce(canvas, fn {row, y}, canvas_acc ->
      Enum.with_index(row)
      |> Enum.reduce(canvas_acc, fn {pixel, x}, inner_acc ->
        # Skip transparent/black pixels
        if pixel > 0 do
          # Calculate position on the canvas
          canvas_x = start_x + x
          canvas_y = start_y + y

          # Only draw if within grid bounds
          if canvas_x >= 0 && canvas_x < grid_width && canvas_y >= 0 && canvas_y < grid_height do
            # Calculate index in the flattened canvas
            index = canvas_y * grid_width + canvas_x

            # Determine color based on position and time
            color_value = PatternHelpers.rem_float(
              (x / art.width) + (y / art.height) + time * 0.1,
              1.0
            )

            # Get color from scheme
            color = PatternHelpers.get_color(color_scheme, color_value, brightness)

            # Replace the pixel in the canvas
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

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      art_size: PatternHelpers.get_param(params, "art_size", state.art_size, :string),
      art_type: PatternHelpers.get_param(params, "art_type", state.art_type, :string),
      display_mode: PatternHelpers.get_param(params, "display_mode", state.display_mode, :string)
    }

    # Update the art if needed
    updated_state = if params["art_size"] != nil || params["art_type"] != nil do
      %{updated_state | current_art: select_pixel_art(updated_state.art_size, updated_state.art_type)}
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Select pixel art based on size and type
  defp select_pixel_art(size, type) do
    case {size, type} do
      # 8x8 Pixel Art
      {"8x8", "retro"} ->
        %{
          width: 8,
          height: 8,
          pixels: [
            [0,0,0,1,1,0,0,0],
            [0,0,1,1,1,1,0,0],
            [0,1,1,1,1,1,1,0],
            [1,1,0,1,1,0,1,1],
            [1,1,1,1,1,1,1,1],
            [0,1,0,1,1,0,1,0],
            [0,0,1,0,0,1,0,0],
            [0,1,0,0,0,0,1,0]
          ]
        }
      {"8x8", "game"} ->
        %{
          width: 8,
          height: 8,
          pixels: [
            [0,0,1,1,1,1,0,0],
            [0,1,0,0,0,0,1,0],
            [1,0,1,0,0,1,0,1],
            [1,0,0,0,0,0,0,1],
            [1,0,1,0,0,1,0,1],
            [1,0,0,1,1,0,0,1],
            [0,1,0,0,0,0,1,0],
            [0,0,1,1,1,1,0,0]
          ]
        }
      {"8x8", "abstract"} ->
        %{
          width: 8,
          height: 8,
          pixels: [
            [0,1,0,0,0,0,1,0],
            [1,0,1,0,0,1,0,1],
            [0,1,0,1,1,0,1,0],
            [0,0,1,0,0,1,0,0],
            [0,0,1,0,0,1,0,0],
            [0,1,0,1,1,0,1,0],
            [1,0,1,0,0,1,0,1],
            [0,1,0,0,0,0,1,0]
          ]
        }
      {"8x8", "emoji"} ->
        %{
          width: 8,
          height: 8,
          pixels: [
            [0,0,1,1,1,1,0,0],
            [0,1,0,0,0,0,1,0],
            [1,0,1,0,0,1,0,1],
            [1,0,0,0,0,0,0,1],
            [1,0,1,1,1,1,0,1],
            [1,0,0,0,0,0,0,1],
            [0,1,0,0,0,0,1,0],
            [0,0,1,1,1,1,0,0]
          ]
        }

      # 12x12 Pixel Art
      {"12x12", "retro"} ->
        %{
          width: 12,
          height: 12,
          pixels: [
            [0,0,0,0,1,1,1,1,0,0,0,0],
            [0,0,0,1,1,1,1,1,1,0,0,0],
            [0,0,1,1,1,1,1,1,1,1,0,0],
            [0,1,1,0,0,1,1,0,0,1,1,0],
            [1,1,1,0,0,1,1,0,0,1,1,1],
            [1,1,1,1,1,1,1,1,1,1,1,1],
            [1,1,1,1,1,1,1,1,1,1,1,1],
            [0,1,1,1,0,0,0,0,1,1,1,0],
            [0,0,1,1,1,0,0,1,1,1,0,0],
            [0,0,0,1,1,1,1,1,1,0,0,0],
            [0,0,0,0,1,1,1,1,0,0,0,0],
            [0,0,0,0,0,1,1,0,0,0,0,0]
          ]
        }
      {"12x12", "game"} ->
        %{
          width: 12,
          height: 12,
          pixels: [
            [0,0,0,0,1,1,1,1,0,0,0,0],
            [0,0,0,1,0,0,0,0,1,0,0,0],
            [0,0,1,0,0,1,1,0,0,1,0,0],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [1,0,0,1,0,0,0,0,1,0,0,1],
            [1,0,1,0,0,0,0,0,0,1,0,1],
            [1,0,1,0,0,1,1,0,0,1,0,1],
            [1,0,0,1,0,0,0,0,1,0,0,1],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [0,0,1,0,0,1,1,0,0,1,0,0],
            [0,0,0,1,0,0,0,0,1,0,0,0],
            [0,0,0,0,1,1,1,1,0,0,0,0]
          ]
        }
      {"12x12", "abstract"} ->
        %{
          width: 12,
          height: 12,
          pixels: [
            [1,0,0,0,0,1,1,0,0,0,0,1],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [0,0,1,1,0,0,0,0,1,1,0,0],
            [0,0,1,0,0,1,1,0,0,1,0,0],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [1,0,0,1,0,0,0,0,1,0,0,1],
            [1,0,0,1,0,0,0,0,1,0,0,1],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [0,0,1,0,0,1,1,0,0,1,0,0],
            [0,0,1,1,0,0,0,0,1,1,0,0],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [1,0,0,0,0,1,1,0,0,0,0,1]
          ]
        }
      {"12x12", "emoji"} ->
        %{
          width: 12,
          height: 12,
          pixels: [
            [0,0,0,1,1,1,1,1,1,0,0,0],
            [0,0,1,0,0,0,0,0,0,1,0,0],
            [0,1,0,0,1,0,0,1,0,0,1,0],
            [1,0,0,0,1,0,0,1,0,0,0,1],
            [1,0,0,0,0,0,0,0,0,0,0,1],
            [1,0,0,0,0,0,0,0,0,0,0,1],
            [1,0,0,1,1,0,0,1,1,0,0,1],
            [1,0,1,0,0,1,1,0,0,1,0,1],
            [1,0,0,1,1,0,0,1,1,0,0,1],
            [0,1,0,0,0,0,0,0,0,0,1,0],
            [0,0,1,0,0,0,0,0,0,1,0,0],
            [0,0,0,1,1,1,1,1,1,0,0,0]
          ]
        }

      # 24x24 Pixel Art
      {"24x24", _} ->
        # For 24x24, we'll create a simplified version for now since it matches our grid size
        # This creates a basic frame pattern
        %{
          width: 24,
          height: 24,
          pixels: Enum.map(0..23, fn y ->
            Enum.map(0..23, fn x ->
              cond do
                x == 0 || x == 23 || y == 0 || y == 23 -> 1
                x > 5 && x < 18 && y > 5 && y < 18 && (x == 6 || x == 17 || y == 6 || y == 17) -> 1
                true -> 0
              end
            end)
          end)
        }

      # Default fallback
      _ ->
        # Default to an 8x8 pixel smiley face
        %{
          width: 8,
          height: 8,
          pixels: [
            [0,0,1,1,1,1,0,0],
            [0,1,0,0,0,0,1,0],
            [1,0,1,0,0,1,0,1],
            [1,0,0,0,0,0,0,1],
            [1,0,1,0,0,1,0,1],
            [1,0,0,1,1,0,0,1],
            [0,1,0,0,0,0,1,0],
            [0,0,1,1,1,1,0,0]
          ]
        }
    end
  end
end
