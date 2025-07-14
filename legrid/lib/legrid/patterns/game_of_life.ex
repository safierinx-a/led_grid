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
        },
        "perturbation_strength" => %{
          type: :float,
          default: 0.05,
          min: 0.0,
          max: 0.2,
          description: "Strength of random perturbations to prevent stalling"
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
      perturbation_strength: PatternHelpers.get_param(params, "perturbation_strength", 0.05, :float),
      # Animation state
      grid: initialize_grid(@default_width, @default_height, PatternHelpers.get_param(params, "initial_density", 0.3, :float)),
      cell_ages: %{},
      time_since_reset: 0.0,
      generation: 0,
      # Performance optimizations
      previous_grid: nil,
      static_count: 0,
      last_update_time: 0.0
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
        generation: 0,
        previous_grid: nil,
        static_count: 0
      }
    else
      # Only update grid based on speed (slower speeds update less frequently)
      update_interval = 1.0 / state.speed

      if time_since_reset - state.generation * update_interval >= update_interval do
        # Update the grid according to Game of Life rules
        {new_grid, new_ages} = update_grid_optimized(state.grid, state.cell_ages, state.wrap_edges, state.width, state.height)

        # Check for static state and apply perturbation if needed
        {final_grid, final_ages, static_count} = handle_static_state(
          new_grid, new_ages, state.grid, state.static_count,
          state.perturbation_strength, state.width, state.height
        )

        %{state |
          grid: final_grid,
          cell_ages: final_ages,
          generation: state.generation + 1,
          time_since_reset: time_since_reset,
          previous_grid: state.grid,
          static_count: static_count
        }
      else
        %{state | time_since_reset: time_since_reset}
      end
    end

    # Generate pixels for the frame
    pixels = render_grid_optimized(state.grid, state.cell_ages, state.width, state.height,
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
      wrap_edges: PatternHelpers.get_param(params, "wrap_edges", state.wrap_edges, :boolean),
      perturbation_strength: PatternHelpers.get_param(params, "perturbation_strength", state.perturbation_strength, :float)
    }

    # Reset grid if initial_density changed significantly
    updated_state = if Map.has_key?(params, "initial_density") &&
                      abs(updated_state.initial_density - state.initial_density) > 0.05 do
      %{updated_state |
        grid: initialize_grid(state.width, state.height, updated_state.initial_density),
        cell_ages: %{},
        generation: 0,
        static_count: 0
      }
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Optimized helper functions

  # Initialize a random grid based on density
  defp initialize_grid(width, height, density) do
    for y <- 0..(height-1), x <- 0..(width-1), into: %{} do
      alive = :rand.uniform() < density
      {{x, y}, alive}
    end
  end

  # Optimized grid update with better performance
  defp update_grid_optimized(grid, ages, wrap_edges, width, height) do
    # Pre-calculate neighbor offsets for better performance
    neighbor_offsets = [
      {-1, -1}, {-1, 0}, {-1, 1},
      {0, -1},           {0, 1},
      {1, -1},  {1, 0},  {1, 1}
    ]

    # Create the next generation grid and updated ages
    Enum.reduce(0..(height-1), {%{}, ages}, fn y, {new_grid, new_ages} ->
      Enum.reduce(0..(width-1), {new_grid, new_ages}, fn x, {grid_acc, ages_acc} ->
        position = {x, y}
        current_state = Map.get(grid, position, false)
        neighbors = count_neighbors_optimized(grid, position, neighbor_offsets, wrap_edges, width, height)

        # Apply Conway's rules
        new_state = cond do
          current_state && (neighbors < 2 || neighbors > 3) -> false  # Dies from loneliness or overcrowding
          current_state && (neighbors == 2 || neighbors == 3) -> true # Survives
          !current_state && neighbors == 3 -> true                    # New cell born
          true -> false                                                # Stays dead
        end

        # Update ages
        new_ages = if new_state do
          current_age = Map.get(ages_acc, position, 0)
          Map.put(ages_acc, position, current_age + 1)
        else
          Map.delete(ages_acc, position)
        end

        {Map.put(grid_acc, position, new_state), new_ages}
      end)
    end)
  end

  # Optimized neighbor counting
  defp count_neighbors_optimized(grid, {x, y}, neighbor_offsets, wrap_edges, width, height) do
    Enum.count(neighbor_offsets, fn {dx, dy} ->
      nx = x + dx
      ny = y + dy

      # Handle wrapping
      {final_x, final_y} = if wrap_edges do
        {rem(nx + width, width), rem(ny + height, height)}
      else
        {nx, ny}
      end

      # Check if neighbor is alive
      Map.get(grid, {final_x, final_y}, false)
    end)
  end

  # Handle static state detection and perturbation
  defp handle_static_state(new_grid, new_ages, previous_grid, static_count, perturbation_strength, width, height) do
    if new_grid == previous_grid do
      # Grid is static, increment counter
      new_static_count = static_count + 1

      if new_static_count >= 5 do
        # Apply perturbation to break static state
        perturbed_grid = apply_perturbation(new_grid, perturbation_strength, width, height)
        {perturbed_grid, new_ages, 0}  # Reset static count
      else
        {new_grid, new_ages, new_static_count}
      end
    else
      {new_grid, new_ages, 0}  # Reset static count
    end
  end

  # Apply random perturbation to break static states
  defp apply_perturbation(grid, strength, width, height) do
    perturbation_count = trunc(width * height * strength)

    Enum.reduce(1..perturbation_count, grid, fn _i, acc ->
      x = :rand.uniform(width) - 1
      y = :rand.uniform(height) - 1
      position = {x, y}

      # Toggle cell state
      current_state = Map.get(acc, position, false)
      Map.put(acc, position, !current_state)
    end)
  end

  # Optimized grid rendering
  defp render_grid_optimized(grid, cell_ages, width, height, cell_age_factor, color_scheme, brightness) do
    for y <- 0..(height-1), x <- 0..(width-1) do
      position = {x, y}
      alive = Map.get(grid, position, false)

      if alive do
        # Get cell age for color variation
        age = Map.get(cell_ages, position, 0)
        age_factor = min(age * cell_age_factor, 1.0)

                # Calculate color based on age and position
        color_value = PatternHelpers.rem_float(
          (x / width) * 0.3 + (y / height) * 0.3 + age_factor * 0.4,
          1.0
        )

        # Use color schemes with gamma correction
        PatternHelpers.get_color(color_scheme, color_value, brightness)
      else
        {0, 0, 0}  # Dead cells are black
      end
    end
  end

  # Legacy functions for compatibility (kept for potential future use)
  # defp update_grid(grid, ages, wrap_edges, width, height) do
  #   update_grid_optimized(grid, ages, wrap_edges, width, height)
  # end

  # defp count_neighbors(grid, position, wrap_edges, width, height) do
  #   neighbor_offsets = [
  #     {-1, -1}, {-1, 0}, {-1, 1},
  #     {0, -1},           {0, 1},
  #     {1, -1},  {1, 0},  {1, 1}
  #   ]
  #   count_neighbors_optimized(grid, position, neighbor_offsets, wrap_edges, width, height)
  # end

  # defp render_grid(grid, cell_ages, width, height, cell_age_factor, color_scheme, brightness) do
  #   render_grid_optimized(grid, cell_ages, width, height, cell_age_factor, color_scheme, brightness)
  # end
end
