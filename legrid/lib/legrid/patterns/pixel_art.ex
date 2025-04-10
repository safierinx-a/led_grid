defmodule Legrid.Patterns.PixelArt do
  @moduledoc """
  Pattern generator for animated pixel art.

  Creates fun pixel art animations inspired by classic 8-bit games,
  featuring randomized sprites, characters, and animations.
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
      id: "pixel_art",
      name: "Pixel Art",
      description: "Animated pixel art sprites and patterns inspired by 8-bit games",
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
        "sprite_type" => %{
          type: :enum,
          default: "random",
          options: ["random", "character", "invader", "tetromino", "pacman", "mario"],
          description: "Type of sprite to display"
        },
        "animation_style" => %{
          type: :enum,
          default: "bounce",
          options: ["bounce", "rotate", "pulse", "blink", "walk", "random"],
          description: "How sprites are animated"
        },
        "sprite_count" => %{
          type: :integer,
          default: 3,
          min: 1,
          max: 10,
          description: "Number of sprites to display"
        },
        "background_pattern" => %{
          type: :enum,
          default: "none",
          options: ["none", "grid", "dots", "stars", "noise"],
          description: "Background pattern type"
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
      sprite_type: PatternHelpers.get_param(params, "sprite_type", "random", :string),
      animation_style: PatternHelpers.get_param(params, "animation_style", "bounce", :string),
      sprite_count: PatternHelpers.get_param(params, "sprite_count", 3, :integer),
      background_pattern: PatternHelpers.get_param(params, "background_pattern", "none", :string),
      # Animation state
      time: 0.0,
      sprites: initialize_sprites(@default_width, @default_height,
                                  PatternHelpers.get_param(params, "sprite_count", 3, :integer),
                                  PatternHelpers.get_param(params, "sprite_type", "random", :string))
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds with speed factor
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update sprites based on animation style
    updated_sprites = update_sprites(state.sprites, state.animation_style, time, state.width, state.height)

    # Generate pixels for the frame
    pixels = render_frame(updated_sprites, state.width, state.height, time,
                          state.background_pattern, state.color_scheme, state.brightness)

    # Create the frame
    frame = Frame.new("pixel_art", state.width, state.height, pixels)

    # Update state with new time and sprites
    new_state = %{state | time: time, sprites: updated_sprites}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Check if we need to reinitialize sprites
    reinitialize = params["sprite_count"] != nil || params["sprite_type"] != nil

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      sprite_type: PatternHelpers.get_param(params, "sprite_type", state.sprite_type, :string),
      animation_style: PatternHelpers.get_param(params, "animation_style", state.animation_style, :string),
      sprite_count: PatternHelpers.get_param(params, "sprite_count", state.sprite_count, :integer),
      background_pattern: PatternHelpers.get_param(params, "background_pattern", state.background_pattern, :string)
    }

    # Reinitialize sprites if needed
    updated_state = if reinitialize do
      %{updated_state | sprites: initialize_sprites(state.width, state.height,
                                                  updated_state.sprite_count,
                                                  updated_state.sprite_type)}
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Initialize sprites based on count and type
  defp initialize_sprites(width, height, count, sprite_type) do
    for _i <- 1..count do
      # Select sprite type (or random if specified)
      actual_type = if sprite_type == "random" do
        Enum.random(["character", "invader", "tetromino", "pacman", "mario"])
      else
        sprite_type
      end

      # Generate sprite data based on type
      sprite_data = generate_sprite_data(actual_type)

      # Add position, velocity and other animation properties
      %{
        type: actual_type,
        data: sprite_data,
        # Random position within bounds
        x: :rand.uniform(width - sprite_data.width),
        y: :rand.uniform(height - sprite_data.height),
        # Random velocity
        vx: (:rand.uniform() * 2 - 1) * 2,
        vy: (:rand.uniform() * 2 - 1) * 2,
        # Animation properties
        phase: :rand.uniform() * 3.14159, # Random starting phase
        frame: 0,
        frame_count: length(sprite_data.frames),
        frame_time: 0.0,
        color_offset: :rand.uniform(),
        scale: 1.0
      }
    end
  end

  # Generate sprite data based on type
  defp generate_sprite_data(type) do
    case type do
      "invader" ->
        %{
          width: 5,
          height: 4,
          frames: [
            [
              [0,1,1,1,0],
              [1,0,1,0,1],
              [1,1,1,1,1],
              [0,1,0,1,0]
            ],
            [
              [0,1,1,1,0],
              [1,0,1,0,1],
              [1,1,1,1,1],
              [1,0,1,0,1]
            ]
          ]
        }

      "character" ->
        %{
          width: 3,
          height: 4,
          frames: [
            [
              [0,1,0],
              [1,1,1],
              [0,1,0],
              [1,0,1]
            ],
            [
              [0,1,0],
              [1,1,1],
              [0,1,0],
              [0,1,1]
            ]
          ]
        }

      "tetromino" ->
        # Pick a random tetromino shape
        shapes = [
          # I piece
          [
            [
              [1,1,1,1]
            ]
          ],
          # O piece
          [
            [
              [1,1],
              [1,1]
            ]
          ],
          # T piece
          [
            [
              [0,1,0],
              [1,1,1]
            ]
          ],
          # L piece
          [
            [
              [1,0],
              [1,0],
              [1,1]
            ]
          ]
        ]

        shape = Enum.random(shapes)
        frame = List.first(shape)

        %{
          width: length(List.first(frame)),
          height: length(frame),
          frames: shape
        }

      "pacman" ->
        %{
          width: 4,
          height: 4,
          frames: [
            [
              [0,1,1,0],
              [1,1,1,0],
              [1,1,0,0],
              [0,1,1,0]
            ],
            [
              [0,1,1,0],
              [1,1,1,1],
              [1,1,1,1],
              [0,1,1,0]
            ]
          ]
        }

      "mario" ->
        %{
          width: 4,
          height: 4,
          frames: [
            [
              [0,1,1,0],
              [0,1,1,1],
              [0,1,1,0],
              [0,1,0,0]
            ],
            [
              [0,1,1,0],
              [0,1,1,1],
              [0,1,1,0],
              [0,0,1,0]
            ]
          ]
        }

      _ ->
        # Default to simple dot
        %{
          width: 1,
          height: 1,
          frames: [
            [
              [1]
            ]
          ]
        }
    end
  end

  # Update sprites based on animation style
  defp update_sprites(sprites, animation_style, time, width, height) do
    Enum.map(sprites, fn sprite ->
      # Update frame for animated sprites
      frame_duration = 0.5
      frame_time = sprite.frame_time + 0.016 # Approximately 60fps

      {new_frame, new_frame_time} = if frame_time >= frame_duration do
        {rem(sprite.frame + 1, sprite.frame_count), 0.0}
      else
        {sprite.frame, frame_time}
      end

      # Apply animation based on style
      sprite = case animation_style do
        "bounce" ->
          # Update position based on velocity
          x = sprite.x + sprite.vx
          y = sprite.y + sprite.vy

          # Bounce off walls
          {x, vx} = if x < 0 || x > width - sprite.data.width do
            {max(0, min(x, width - sprite.data.width)), -sprite.vx}
          else
            {x, sprite.vx}
          end

          {y, vy} = if y < 0 || y > height - sprite.data.height do
            {max(0, min(y, height - sprite.data.height)), -sprite.vy}
          else
            {y, sprite.vy}
          end

          %{sprite | x: x, y: y, vx: vx, vy: vy}

        "rotate" ->
          # Rotate around center
          center_x = width / 2
          center_y = height / 2
          radius = min(width, height) / 3

          x = center_x + radius * :math.cos(time + sprite.phase)
          y = center_y + radius * :math.sin(time + sprite.phase)

          %{sprite | x: x - sprite.data.width / 2, y: y - sprite.data.height / 2}

        "pulse" ->
          # Pulse size
          scale = 0.8 + 0.4 * :math.sin(time * 2 + sprite.phase)
          %{sprite | scale: scale}

        "blink" ->
          # Just update frame
          sprite

        "walk" ->
          # Simple left-right movement
          x = rem(trunc(sprite.x + time * 3), width)
          %{sprite | x: x}

        "random" ->
          # Random animation style for each sprite
          random_style = Enum.random(["bounce", "rotate", "pulse", "blink", "walk"])
          update_sprites([sprite], random_style, time, width, height) |> List.first()

        _ ->
          # Default to just updating frame
          sprite
      end

      # Update frame counters
      %{sprite | frame: new_frame, frame_time: new_frame_time}
    end)
  end

  # Render a frame with sprites and background
  defp render_frame(sprites, width, height, time, background_pattern, color_scheme, brightness) do
    # Create empty background
    canvas = for _y <- 0..(height-1), _x <- 0..(width-1), do: {0, 0, 0}

    # Add background pattern if enabled
    canvas = case background_pattern do
      "grid" -> render_background_grid(canvas, width, height, time, color_scheme, brightness * 0.3)
      "dots" -> render_background_dots(canvas, width, height, time, color_scheme, brightness * 0.3)
      "stars" -> render_background_stars(canvas, width, height, time, color_scheme, brightness * 0.3)
      "noise" -> render_background_noise(canvas, width, height, time, color_scheme, brightness * 0.3)
      _ -> canvas # No background
    end

    # Render each sprite onto the canvas
    Enum.reduce(sprites, canvas, fn sprite, acc ->
      # Get current frame data
      frame_data = Enum.at(sprite.data.frames, sprite.frame)

      # Render the sprite at its position with appropriate color
      render_sprite(acc, frame_data, sprite, width, height, time, color_scheme, brightness)
    end)
  end

  # Render a sprite onto the canvas
  defp render_sprite(canvas, frame_data, sprite, width, height, time, color_scheme, brightness) do
    # Calculate base coordinates for sprite
    base_x = trunc(sprite.x)
    base_y = trunc(sprite.y)

    # Iterate through the sprite's pixels
    Enum.with_index(frame_data)
    |> Enum.reduce(canvas, fn {row, y}, canvas_acc ->
      Enum.with_index(row)
      |> Enum.reduce(canvas_acc, fn {pixel, x}, inner_acc ->
        if pixel > 0 do
          # Calculate position on the canvas
          canvas_x = base_x + x
          canvas_y = base_y + y

          # Only draw if within bounds
          if canvas_x >= 0 && canvas_x < width && canvas_y >= 0 && canvas_y < height do
            # Calculate index in the flattened canvas
            index = canvas_y * width + canvas_x

            # Calculate color based on sprite properties
            color_value = PatternHelpers.rem_float(sprite.color_offset + time * 0.1, 1.0)

            # Determine color from scheme
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

  # Render grid background pattern
  defp render_background_grid(canvas, width, height, time, color_scheme, brightness) do
    grid_size = 4
    color_factor = 0.05

    Enum.with_index(Enum.chunk_every(canvas, width))
    |> Enum.flat_map(fn {row, y} ->
      Enum.with_index(row)
      |> Enum.map(fn {{_r, _g, _b}, x} ->
        # Draw grid lines
        if rem(x, grid_size) == 0 || rem(y, grid_size) == 0 do
          color_value = PatternHelpers.rem_float(time * color_factor, 1.0)
          PatternHelpers.get_color(color_scheme, color_value, brightness * 0.7)
        else
          {0, 0, 0}
        end
      end)
    end)
  end

  # Render dots background pattern
  defp render_background_dots(canvas, width, height, time, color_scheme, brightness) do
    Enum.with_index(Enum.chunk_every(canvas, width))
    |> Enum.flat_map(fn {row, y} ->
      Enum.with_index(row)
      |> Enum.map(fn {{_r, _g, _b}, x} ->
        # Draw dots in a pattern
        if rem(x + y, 6) == 0 do
          color_value = PatternHelpers.rem_float((x * 0.1 + y * 0.1) + time * 0.1, 1.0)
          PatternHelpers.get_color(color_scheme, color_value, brightness * 0.6)
        else
          {0, 0, 0}
        end
      end)
    end)
  end

  # Render stars background pattern
  defp render_background_stars(canvas, width, height, time, color_scheme, brightness) do
    # Determine star positions (pseudorandom but stable)
    star_positions = for i <- 1..20 do
      x = rem(i * 631, width)
      y = rem(i * 743, height)

      # Star twinkle factor
      twinkle = :math.sin(time * 2 + i * 0.5) * 0.5 + 0.5

      {x, y, twinkle}
    end

    # Draw stars
    Enum.with_index(Enum.chunk_every(canvas, width))
    |> Enum.flat_map(fn {row, y} ->
      Enum.with_index(row)
      |> Enum.map(fn {{_r, _g, _b}, x} ->
        # Check if current position is a star
        case Enum.find(star_positions, fn {sx, sy, _} -> sx == x && sy == y end) do
          {_, _, twinkle} ->
            color_value = PatternHelpers.rem_float(time * 0.05 + x * y * 0.001, 1.0)
            {r, g, b} = PatternHelpers.get_color(color_scheme, color_value, brightness * twinkle)
            {r, g, b}

          nil ->
            {0, 0, 0}
        end
      end)
    end)
  end

  # Render noise background pattern
  defp render_background_noise(canvas, width, height, time, color_scheme, brightness) do
    # Use time to seed the noise
    seed = trunc(time * 10)

    Enum.with_index(Enum.chunk_every(canvas, width))
    |> Enum.flat_map(fn {row, y} ->
      Enum.with_index(row)
      |> Enum.map(fn {{_r, _g, _b}, x} ->
        # Generate pseudo-random noise
        noise_val = :rand.uniform(100)

        if noise_val < 10 do
          color_value = PatternHelpers.rem_float(x * y * 0.001 + time * 0.1, 1.0)
          PatternHelpers.get_color(color_scheme, color_value, brightness * 0.5)
        else
          {0, 0, 0}
        end
      end)
    end)
  end
end
