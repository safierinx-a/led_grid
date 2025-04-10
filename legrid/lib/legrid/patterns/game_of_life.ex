defmodule Legrid.Patterns.GameOfLife do
  @moduledoc """
  Pattern generator for Conway's Game of Life.

  Implements the classic cellular automaton with customizable parameters
  for colors, initial density, and update speed.
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
      id: "game_of_life",
      name: "Game of Life",
      description: "Conway's Game of Life cellular automaton with colorful cells",
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
        "initial_density" => %{
          type: :float,
          default: 0.3,
          min: 0.1,
          max: 0.9,
          description: "Initial cell density (randomness)"
        },
        "cell_age_factor" => %{
          type: :float,
          default: 0.1,
          min: 0.0,
          max: 1.0,
          description: "How quickly cell colors change with age"
        },
        "reset_interval" => %{
          type: :float,
          default: 0.0,
          min: 0.0,
          max: 120.0,
          description: "Seconds between resets (0 = never reset)"
        },
        "wrap_edges" => %{
          type: :boolean,
          default: true,
          description: "Whether cells wrap around grid edges"
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
      initial_density: PatternHelpers.get_param(params, "initial_density", 0.3, :float),
      cell_age_factor: PatternHelpers.get_param(params, "cell_age_factor", 0.1, :float),
      reset_interval: PatternHelpers.get_param(params, "reset_interval", 0.0, :float),
      wrap_edges: PatternHelpers.get_param(params, "wrap_edges", true, :boolean),
      # Animation state
      grid: initialize_grid(@default_width, @default_height, PatternHelpers.get_param(params, "initial_density", 0.3, :float)),
      cell_ages: %{},
      time_since_reset: 0.0,
      generation: 0
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Convert elapsed time to seconds
    delta_time = elapsed_ms / 1000.0

    # Update time since last reset
    time_since_reset = state.time_since_reset + delta_time

    # Check if it's time to reset
    state = if state.reset_interval > 0 && time_since_reset >= state.reset_interval do
      %{state |
        grid: initialize_grid(state.width, state.height, state.initial_density),
        cell_ages: %{},
        time_since_reset: 0.0,
        generation: 0
      }
    else
      # Only update grid based on speed (slower speeds update less frequently)
      update_interval = 1.0 / state.speed

      if time_since_reset - state.generation * update_interval >= update_interval do
        # Update the grid according to Game of Life rules
        {new_grid, new_ages} = update_grid(state.grid, state.cell_ages, state.wrap_edges, state.width, state.height)

        %{state |
          grid: new_grid,
          cell_ages: new_ages,
          generation: state.generation + 1,
          time_since_reset: time_since_reset
        }
      else
        %{state | time_since_reset: time_since_reset}
      end
    end

    # Generate pixels for the frame
    pixels = render_grid(state.grid, state.cell_ages, state.width, state.height,
                        state.cell_age_factor, state.color_scheme, state.brightness)

    # Create the frame
    frame = Frame.new("game_of_life", state.width, state.height, pixels)

    {:ok, frame, state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      initial_density: PatternHelpers.get_param(params, "initial_density", state.initial_density, :float),
      cell_age_factor: PatternHelpers.get_param(params, "cell_age_factor", state.cell_age_factor, :float),
      reset_interval: PatternHelpers.get_param(params, "reset_interval", state.reset_interval, :float),
      wrap_edges: PatternHelpers.get_param(params, "wrap_edges", state.wrap_edges, :boolean)
    }

    # Reset grid if initial_density changed significantly
    updated_state = if Map.has_key?(params, "initial_density") &&
                      abs(updated_state.initial_density - state.initial_density) > 0.05 do
      %{updated_state |
        grid: initialize_grid(state.width, state.height, updated_state.initial_density),
        cell_ages: %{},
        generation: 0
      }
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Initialize a random grid based on density
  defp initialize_grid(width, height, density) do
    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      alive = :rand.uniform() < density
      {{x, y}, alive}
    end
  end

  # Update the grid according to Game of Life rules
  defp update_grid(grid, ages, wrap_edges, width, height) do
    # Create the next generation grid and updated ages
    Enum.reduce(0..(height-1), {%{}, ages}, fn y, {new_grid, new_ages} ->
      Enum.reduce(0..(width-1), {new_grid, new_ages}, fn x, {grid_acc, ages_acc} ->
        position = {x, y}
        current_state = Map.get(grid, position, false)
        neighbors = count_neighbors(grid, position, wrap_edges, width, height)

        # Apply Conway's rules
        new_state = cond do
          current_state && (neighbors < 2 || neighbors > 3) -> false  # Dies from loneliness or overcrowding
          current_state && (neighbors == 2 || neighbors == 3) -> true # Survives
          !current_state && neighbors == 3 -> true                    # New cell born
          true -> false                                               # Remains dead
        end

        # Update cell age for living cells
        ages_acc = if new_state do
          # Increment age for living cells, or set to 1 for newly born cells
          Map.put(ages_acc, position, Map.get(ages_acc, position, 0) + 1)
        else
          # Remove dead cells from the ages map
          Map.delete(ages_acc, position)
        end

        {Map.put(grid_acc, position, new_state), ages_acc}
      end)
    end)
  end

  # Count living neighbors for a cell
  defp count_neighbors(grid, {x, y}, wrap_edges, width, height) do
    # Define the 8 neighboring positions
    neighbors = for dx <- -1..1, dy <- -1..1, {dx, dy} != {0, 0} do
      if wrap_edges do
        # Wrap around edges
        {rem(x + dx + width, width), rem(y + dy + height, height)}
      else
        # Check bounds
        nx = x + dx
        ny = y + dy
        if nx >= 0 && nx < width && ny >= 0 && ny < height do
          {nx, ny}
        else
          nil
        end
      end
    end

    # Filter out nil positions and count living cells
    neighbors
    |> Enum.reject(&is_nil/1)
    |> Enum.count(fn pos -> Map.get(grid, pos, false) end)
  end

  # Render the grid to pixels
  defp render_grid(grid, ages, width, height, age_factor, color_scheme, brightness) do
    for y <- 0..(height-1), x <- 0..(width-1) do
      position = {x, y}
      alive = Map.get(grid, position, false)

      if alive do
        # Get the cell's age and use it to determine color
        age = Map.get(ages, position, 0)
        color_value = PatternHelpers.rem_float(age * age_factor, 1.0)

        # Determine brightness based on newness of cell
        age_brightness = min(1.0, 0.5 + (1 / (age * 0.1 + 1)))

        # Get color based on scheme and brightness
        PatternHelpers.get_color(color_scheme, color_value, brightness * age_brightness)
      else
        # Return black for dead cells
        {0, 0, 0}
      end
    end
  end
end
