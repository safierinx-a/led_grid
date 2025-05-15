defmodule Legrid.Patterns.WaveModulation do
  @moduledoc """
  Pattern generator for complex wave modulation patterns.

  Creates intricate patterns using multiple interacting waves with
  frequency and amplitude modulation between them.
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
      id: "wave_modulation",
      name: "Wave Modulation",
      description: "Complex interacting wave patterns with frequency and amplitude modulation",
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
        "wave_type" => %{
          type: :enum,
          default: "frequency_modulation",
          options: ["frequency_modulation", "amplitude_modulation", "phase_modulation", "harmonics", "interference"],
          description: "Type of wave modulation"
        },
        "complexity" => %{
          type: :float,
          default: 0.5,
          min: 0.1,
          max: 1.0,
          description: "Complexity of wave patterns"
        },
        "wave_count" => %{
          type: :integer,
          default: 3,
          min: 1,
          max: 5,
          description: "Number of interacting waves"
        },
        "symmetry" => %{
          type: :enum,
          default: "none",
          options: ["none", "horizontal", "vertical", "radial", "rotational"],
          description: "Type of symmetry in the pattern"
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
      wave_type: PatternHelpers.get_param(params, "wave_type", "frequency_modulation", :string),
      complexity: PatternHelpers.get_param(params, "complexity", 0.5, :float),
      wave_count: PatternHelpers.get_param(params, "wave_count", 3, :integer),
      symmetry: PatternHelpers.get_param(params, "symmetry", "none", :string),
      # Animation state
      time: 0.0,
      # Wave parameters
      waves: initialize_waves(
        PatternHelpers.get_param(params, "wave_count", 3, :integer),
        PatternHelpers.get_param(params, "wave_type", "frequency_modulation", :string),
        PatternHelpers.get_param(params, "complexity", 0.5, :float)
      )
    }

    {:ok, state}
  end

  @impl true
  def render(state, elapsed_ms) do
    # Update time
    delta_time = elapsed_ms / 1000.0 * state.speed
    time = state.time + delta_time

    # Update wave parameters subtly over time
    waves = update_wave_parameters(state.waves, time, state.wave_type, state.complexity)

    # Generate pixels for the frame
    pixels = generate_wave_pattern(
      state.width,
      state.height,
      time,
      waves,
      state.wave_type,
      state.symmetry,
      state.color_scheme,
      state.brightness
    )

    # Create the frame
    frame = Frame.new("wave_modulation", state.width, state.height, pixels)

    # Update state
    new_state = %{state | time: time, waves: waves}

    {:ok, frame, new_state}
  end

  @impl true
  def update_params(state, params) do
    # Apply global parameters
    updated_state = PatternHelpers.apply_global_params(state, params)

    # Check if we need to reinitialize waves
    reinitialize = Map.has_key?(params, "wave_count") ||
                   Map.has_key?(params, "wave_type") ||
                   (Map.has_key?(params, "complexity") &&
                    abs(PatternHelpers.get_param(params, "complexity", state.complexity, :float) - state.complexity) > 0.2)

    # Apply pattern-specific parameters
    updated_state = %{updated_state |
      wave_type: PatternHelpers.get_param(params, "wave_type", state.wave_type, :string),
      complexity: PatternHelpers.get_param(params, "complexity", state.complexity, :float),
      wave_count: PatternHelpers.get_param(params, "wave_count", state.wave_count, :integer),
      symmetry: PatternHelpers.get_param(params, "symmetry", state.symmetry, :string)
    }

    # Reinitialize waves if needed
    updated_state = if reinitialize do
      %{updated_state | waves: initialize_waves(
        updated_state.wave_count,
        updated_state.wave_type,
        updated_state.complexity
      )}
    else
      updated_state
    end

    {:ok, updated_state}
  end

  # Helper functions

  # Initialize wave parameters
  defp initialize_waves(count, wave_type, complexity) do
    for i <- 1..count do
      # Base frequency and amplitude vary by wave index
      base_freq = 0.5 + i * 0.5 * complexity
      base_amp = 1.0 / i

      # Different parameters based on wave type
      case wave_type do
        "frequency_modulation" ->
          %{
            base_frequency: base_freq,
            base_amplitude: base_amp,
            modulation_depth: 0.2 + :rand.uniform() * 0.5 * complexity,
            modulation_rate: 0.1 + :rand.uniform() * 0.3 * complexity,
            phase_offset: :rand.uniform() * 2 * :math.pi,
            direction_x: :rand.uniform() * 2 - 1,
            direction_y: :rand.uniform() * 2 - 1
          }

        "amplitude_modulation" ->
          %{
            base_frequency: base_freq,
            base_amplitude: base_amp,
            modulation_depth: 0.5 + :rand.uniform() * 0.5 * complexity,
            modulation_rate: 0.05 + :rand.uniform() * 0.2 * complexity,
            phase_offset: :rand.uniform() * 2 * :math.pi,
            direction_x: :rand.uniform() * 2 - 1,
            direction_y: :rand.uniform() * 2 - 1
          }

        "phase_modulation" ->
          %{
            base_frequency: base_freq,
            base_amplitude: base_amp,
            modulation_depth: :math.pi * (0.2 + :rand.uniform() * 0.8 * complexity),
            modulation_rate: 0.05 + :rand.uniform() * 0.3 * complexity,
            phase_offset: :rand.uniform() * 2 * :math.pi,
            direction_x: :rand.uniform() * 2 - 1,
            direction_y: :rand.uniform() * 2 - 1
          }

        "harmonics" ->
          %{
            base_frequency: base_freq,
            base_amplitude: base_amp,
            harmonic_count: trunc(2 + :rand.uniform(5) * complexity),
            amplitude_falloff: 0.5 + :rand.uniform() * 0.3,
            phase_offset: :rand.uniform() * 2 * :math.pi,
            direction_x: :rand.uniform() * 2 - 1,
            direction_y: :rand.uniform() * 2 - 1
          }

        "interference" ->
          %{
            frequency1: base_freq,
            frequency2: base_freq * (1.0 + 0.1 * :rand.uniform() * complexity),
            amplitude1: base_amp,
            amplitude2: base_amp * (0.8 + 0.4 * :rand.uniform()),
            phase_offset1: :rand.uniform() * 2 * :math.pi,
            phase_offset2: :rand.uniform() * 2 * :math.pi,
            direction_x1: :rand.uniform() * 2 - 1,
            direction_y1: :rand.uniform() * 2 - 1,
            direction_x2: :rand.uniform() * 2 - 1,
            direction_y2: :rand.uniform() * 2 - 1
          }
      end
    end
  end

  # Update wave parameters over time for subtle evolution
  defp update_wave_parameters(waves, time, wave_type, complexity) do
    evolution_rate = 0.03 * complexity

    Enum.map(waves, fn wave ->
      case wave_type do
        "frequency_modulation" ->
          # Slowly vary modulation depth and rate
          mod_depth_variation = wave.modulation_depth + :math.sin(time * 0.11) * 0.05 * evolution_rate
          mod_rate_variation = wave.modulation_rate + :math.cos(time * 0.07) * 0.02 * evolution_rate

          %{wave |
            modulation_depth: mod_depth_variation,
            modulation_rate: mod_rate_variation
          }

        "amplitude_modulation" ->
          # Vary modulation depth and base amplitude
          mod_depth_variation = wave.modulation_depth + :math.sin(time * 0.13) * 0.1 * evolution_rate
          base_amp_variation = wave.base_amplitude + :math.cos(time * 0.09) * 0.05 * evolution_rate

          %{wave |
            modulation_depth: mod_depth_variation,
            base_amplitude: max(0.1, base_amp_variation)
          }

        "phase_modulation" ->
          # Vary modulation depth
          mod_depth_variation = wave.modulation_depth + :math.sin(time * 0.08) * 0.2 * evolution_rate

          %{wave |
            modulation_depth: mod_depth_variation
          }

        "harmonics" ->
          # Vary amplitude falloff
          falloff_variation = wave.amplitude_falloff + :math.sin(time * 0.1) * 0.05 * evolution_rate

          %{wave |
            amplitude_falloff: max(0.1, min(0.9, falloff_variation))
          }

        "interference" ->
          # Vary frequency relationship
          freq2_variation = wave.frequency1 * (1.0 + 0.1 * :math.sin(time * 0.12) * evolution_rate)

          %{wave |
            frequency2: freq2_variation
          }
      end
    end)
  end

  # Generate wave pattern pixels
  defp generate_wave_pattern(width, height, time, waves, wave_type, symmetry, color_scheme, brightness) do
    for y <- 0..(height-1), x <- 0..(width-1) do
      # Normalize coordinates
      nx = x / width
      ny = y / height

      # Apply symmetry transformation if needed
      {sample_x, sample_y} = apply_symmetry(nx, ny, symmetry)

      # Calculate wave value at this point
      {value, phase} = calculate_wave_value(sample_x, sample_y, time, waves, wave_type)

      # Map value to brightness (normalized to 0.0-1.0)
      value_normalized = (value + 1.0) / 2.0

      # Use phase information for color variation
      color_value = PatternHelpers.rem_float(phase / (2 * :math.pi) + time * 0.1, 1.0)

      # Apply brightness based on wave value
      pixel_brightness = value_normalized * brightness

      # Get color from scheme
      PatternHelpers.get_color(color_scheme, color_value, pixel_brightness)
    end
  end

  # Apply symmetry transformation to coordinates
  defp apply_symmetry(x, y, symmetry) do
    case symmetry do
      "horizontal" ->
        # Reflect across horizontal middle line
        {x, abs(y - 0.5) + 0.5}

      "vertical" ->
        # Reflect across vertical middle line
        {abs(x - 0.5) + 0.5, y}

      "radial" ->
        # Distance from center determines the pattern
        dx = x - 0.5
        dy = y - 0.5
        distance = :math.sqrt(dx * dx + dy * dy)
        angle = :math.atan2(dy, dx)
        {distance * 2, PatternHelpers.rem_float(angle / (2 * :math.pi), 1.0)}

      "rotational" ->
        # Rotate coordinates around center
        dx = x - 0.5
        dy = y - 0.5
        distance = :math.sqrt(dx * dx + dy * dy)
        angle = :math.atan2(dy, dx)
        # 3-fold rotational symmetry
        angle_mod = PatternHelpers.rem_float(angle * 3 / (2 * :math.pi), 1.0)
        {distance * 2, angle_mod}

      _ ->
        # No symmetry
        {x, y}
    end
  end

  # Calculate wave value based on coordinates, time, and wave parameters
  defp calculate_wave_value(x, y, time, waves, wave_type) do
    case wave_type do
      "frequency_modulation" ->
        # Each wave modulates the frequency of the carrier wave
        # Start with a base value
        Enum.reduce(waves, {0.0, 0.0}, fn wave, {acc_value, acc_phase} ->
          # Calculate the modulation
          mod_val = wave.modulation_depth * :math.sin(time * wave.modulation_rate)

          # Calculate phase including directional component and modulation
          phase = wave.base_frequency * (1.0 + mod_val) *
                 (x * wave.direction_x + y * wave.direction_y) +
                 time * wave.base_frequency + wave.phase_offset

          # Calculate output and phase
          output = wave.base_amplitude * :math.sin(phase)

          # Sum with accumulator
          {acc_value + output, acc_phase + phase}
        end)

      "amplitude_modulation" ->
        # Each wave amplitude-modulates the carrier wave
        Enum.reduce(waves, {0.0, 0.0}, fn wave, {acc_value, acc_phase} ->
          # Calculate the carrier signal phase
          carrier_phase = wave.base_frequency *
                          (x * wave.direction_x + y * wave.direction_y) +
                          time * wave.base_frequency + wave.phase_offset

          # Calculate the modulation signal
          mod_val = 1.0 + wave.modulation_depth * :math.sin(time * wave.modulation_rate)

          # Apply amplitude modulation
          output = wave.base_amplitude * mod_val * :math.sin(carrier_phase)

          # Sum with accumulator
          {acc_value + output, acc_phase + carrier_phase}
        end)

      "phase_modulation" ->
        # Each wave phase-modulates the carrier wave
        Enum.reduce(waves, {0.0, 0.0}, fn wave, {acc_value, acc_phase} ->
          # Calculate modulator phase
          mod_phase = time * wave.modulation_rate

          # Calculate modulation signal
          mod_val = wave.modulation_depth * :math.sin(mod_phase)

          # Calculate carrier phase with phase modulation
          carrier_phase = wave.base_frequency *
                         (x * wave.direction_x + y * wave.direction_y) +
                         time * wave.base_frequency +
                         mod_val + wave.phase_offset

          # Calculate output
          output = wave.base_amplitude * :math.sin(carrier_phase)

          # Sum with accumulator
          {acc_value + output, acc_phase + carrier_phase}
        end)

      "harmonics" ->
        # Each wave contributes harmonics
        Enum.reduce(waves, {0.0, 0.0}, fn wave, {acc_value, acc_phase} ->
          # Sum the harmonics
          {value, phase} = Enum.reduce(1..wave.harmonic_count, {0.0, 0.0}, fn harmonic, {harm_acc, phase_acc} ->
            # Calculate amplitude for this harmonic
            amplitude = wave.base_amplitude * :math.pow(wave.amplitude_falloff, harmonic - 1)

            # Calculate phase for this harmonic
            harm_phase = harmonic * wave.base_frequency *
                        (x * wave.direction_x + y * wave.direction_y) +
                        time * harmonic * wave.base_frequency +
                        wave.phase_offset

            # Calculate output for this harmonic
            harm_output = amplitude * :math.sin(harm_phase)

            # Sum with harmonic accumulator
            {harm_acc + harm_output, phase_acc + harm_phase}
          end)

          # Sum with main accumulator
          {acc_value + value, acc_phase + phase}
        end)

      "interference" ->
        # Waves create interference patterns
        Enum.reduce(waves, {0.0, 0.0}, fn wave, {acc_value, acc_phase} ->
          # Calculate phase for first wave
          phase1 = wave.frequency1 *
                  (x * wave.direction_x1 + y * wave.direction_y1) +
                  time * wave.frequency1 + wave.phase_offset1

          # Calculate phase for second wave
          phase2 = wave.frequency2 *
                  (x * wave.direction_x2 + y * wave.direction_y2) +
                  time * wave.frequency2 + wave.phase_offset2

          # Calculate outputs
          output1 = wave.amplitude1 * :math.sin(phase1)
          output2 = wave.amplitude2 * :math.sin(phase2)

          # Combine waves and their phases
          combined_output = output1 + output2
          combined_phase = (phase1 + phase2) / 2

          # Sum with accumulator
          {acc_value + combined_output, acc_phase + combined_phase}
        end)
    end
  end
end
