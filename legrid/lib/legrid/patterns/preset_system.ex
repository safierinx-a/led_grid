defmodule Legrid.Patterns.PresetSystem do
  @moduledoc """
  Preset system for saving and loading pattern configurations.

  Provides built-in presets and user-customizable presets
  for quick pattern switching and configuration management.
  """

  @presets_file "config/pattern_presets.json"

  @doc """
  Get all available presets (built-in + user presets).
  """
  def get_all_presets do
    built_in = get_built_in_presets()
    user_presets = get_user_presets()

    Map.merge(built_in, user_presets)
  end

  @doc """
  Get built-in presets that come with the system.
  """
  def get_built_in_presets do
    %{
      "calm_ocean" => %{
        name: "Calm Ocean",
        description: "Gentle blue waves with low intensity",
        pattern: "sine_field",
        parameters: %{
          "brightness" => 0.6,
          "color_scheme" => "enhanced_ocean",
          "speed" => 0.3,
          "amplitude" => 0.5,
          "frequency" => 1.0
        }
      },
      "vibrant_fire" => %{
        name: "Vibrant Fire",
        description: "Bright fire effect with high energy",
        pattern: "flow_field",
        parameters: %{
          "brightness" => 0.9,
          "color_scheme" => "enhanced_fire",
          "speed" => 0.8,
          "field_strength" => 0.7,
          "particle_count" => 50
        }
      },
      "gentle_rainbow" => %{
        name: "Gentle Rainbow",
        description: "Soft rainbow colors with smooth transitions",
        pattern: "sine_field",
        parameters: %{
          "brightness" => 0.7,
          "color_scheme" => "enhanced_rainbow",
          "speed" => 0.4,
          "amplitude" => 0.6,
          "frequency" => 0.8
        }
      },
      "matrix_rain" => %{
        name: "Matrix Rain",
        description: "Digital green matrix effect",
        pattern: "game_of_life",
        parameters: %{
          "brightness" => 0.8,
          "color_scheme" => "enhanced_monochrome",
          "speed" => 0.6,
          "initial_density" => 0.4,
          "cell_age_factor" => 0.2
        }
      },
      "aurora_borealis" => %{
        name: "Aurora Borealis",
        description: "Northern lights effect with green and purple",
        pattern: "flow_field",
        parameters: %{
          "brightness" => 0.7,
          "color_scheme" => "enhanced_forest",
          "speed" => 0.5,
          "field_strength" => 0.6,
          "particle_count" => 40
        }
      },
      "clock_display" => %{
        name: "Clock Display",
        description: "Clear digital clock with good readability",
        pattern: "clock",
        parameters: %{
          "brightness" => 0.9,
          "color_scheme" => "enhanced_monochrome",
          "speed" => 1.0,
          "clock_type" => "digital",
          "show_seconds" => true,
          "use_24h" => false
        }
      },
      "optical_illusion" => %{
        name: "Optical Illusion",
        description: "Hypnotic moving patterns",
        pattern: "optical_illusion",
        parameters: %{
          "brightness" => 0.8,
          "color_scheme" => "enhanced_neon",
          "speed" => 0.7,
          "illusion_type" => "spiral",
          "rotation_speed" => 0.5
        }
      },
      "zen_garden" => %{
        name: "Zen Garden",
        description: "Peaceful, minimal pattern",
        pattern: "sine_field",
        parameters: %{
          "brightness" => 0.5,
          "color_scheme" => "enhanced_pastel",
          "speed" => 0.2,
          "amplitude" => 0.3,
          "frequency" => 0.5
        }
      },
      "party_mode" => %{
        name: "Party Mode",
        description: "High energy, colorful patterns",
        pattern: "flow_field",
        parameters: %{
          "brightness" => 1.0,
          "color_scheme" => "enhanced_rainbow",
          "speed" => 1.2,
          "field_strength" => 0.8,
          "particle_count" => 60
        }
      },
      "night_mode" => %{
        name: "Night Mode",
        description: "Low brightness for dark environments",
        pattern: "sine_field",
        parameters: %{
          "brightness" => 0.3,
          "color_scheme" => "enhanced_ocean",
          "speed" => 0.3,
          "amplitude" => 0.4,
          "frequency" => 0.6
        }
      },
      "classic_rose" => %{
        name: "Classic Rose",
        description: "A beautiful 6-petal rose curve in rainbow colors",
        pattern: "parametric_curve",
        parameters: %{"curve_type" => "rose", "petals" => 6, "color_scheme" => "enhanced_rainbow", "brightness" => 0.9, "speed" => 0.4}
      },
      "spiral_galaxy" => %{
        name: "Spiral Galaxy",
        description: "Animated spiral with neon colors",
        pattern: "parametric_curve",
        parameters: %{"curve_type" => "spiral", "a" => 1.0, "b" => 0.5, "color_scheme" => "enhanced_neon", "brightness" => 0.8, "speed" => 0.6}
      },
      "heart" => %{
        name: "Heart",
        description: "Cardioid curve in sunset colors",
        pattern: "parametric_curve",
        parameters: %{"curve_type" => "cardioid", "color_scheme" => "enhanced_sunset", "brightness" => 0.85, "speed" => 0.5}
      },
      "butterfly" => %{
        name: "Butterfly",
        description: "Butterfly curve with pastel colors",
        pattern: "parametric_curve",
        parameters: %{"curve_type" => "butterfly", "color_scheme" => "enhanced_pastel", "brightness" => 0.9, "speed" => 0.7}
      },
      "lemniscate" => %{
        name: "Lemniscate",
        description: "Lemniscate of Bernoulli in ocean colors",
        pattern: "parametric_curve",
        parameters: %{"curve_type" => "lemniscate", "color_scheme" => "enhanced_ocean", "brightness" => 0.8, "speed" => 0.5}
      }
    }
  end

  @doc """
  Get user-defined presets from file.
  """
  def get_user_presets do
    case File.read(@presets_file) do
      {:ok, content} ->
        case Jason.decode(content) do
          {:ok, presets} -> presets
          _ -> %{}
        end
      _ -> %{}
    end
  end

  @doc """
  Save a user preset.
  """
  def save_user_preset(id, preset_data) do
    # Validate preset data
    case validate_preset(preset_data) do
      {:ok, validated_preset} ->
        # Load existing presets
        existing_presets = get_user_presets()

        # Add new preset
        updated_presets = Map.put(existing_presets, id, validated_preset)

        # Save to file
        case save_presets_to_file(updated_presets) do
          :ok -> {:ok, "Preset '#{id}' saved successfully"}
          {:error, reason} -> {:error, "Failed to save preset: #{reason}"}
        end

      {:error, reason} ->
        {:error, "Invalid preset data: #{reason}"}
    end
  end

  @doc """
  Delete a user preset.
  """
  def delete_user_preset(id) do
    existing_presets = get_user_presets()

    case Map.get(existing_presets, id) do
      nil ->
        {:error, "Preset '#{id}' not found"}

      _ ->
        updated_presets = Map.delete(existing_presets, id)

        case save_presets_to_file(updated_presets) do
          :ok -> {:ok, "Preset '#{id}' deleted successfully"}
          {:error, reason} -> {:error, "Failed to delete preset: #{reason}"}
        end
    end
  end

  @doc """
  Get a specific preset by ID.
  """
  def get_preset(id) do
    all_presets = get_all_presets()
    Map.get(all_presets, id)
  end

  @doc """
  Apply a preset to a pattern state.
  """
  def apply_preset(state, preset_id) do
    case get_preset(preset_id) do
      nil ->
        {:error, "Preset '#{preset_id}' not found"}

      preset ->
        # Update state with preset parameters
        updated_state = %{state |
          pattern: preset.parameters["pattern"] || state.pattern,
          brightness: preset.parameters["brightness"] || state.brightness,
          color_scheme: preset.parameters["color_scheme"] || state.color_scheme,
          speed: preset.parameters["speed"] || state.speed
        }

        # Apply pattern-specific parameters
        pattern_params = Map.drop(preset.parameters, ["pattern", "brightness", "color_scheme", "speed"])

        updated_state = Enum.reduce(pattern_params, updated_state, fn {key, value}, acc ->
          Map.put(acc, key, value)
        end)

        {:ok, updated_state}
    end
  end

  @doc """
  List all available presets with descriptions.
  """
  def list_presets do
    all_presets = get_all_presets()

    Enum.map(all_presets, fn {id, preset} ->
      %{
        id: id,
        name: preset.name,
        description: preset.description,
        pattern: preset.parameters["pattern"]
      }
    end)
  end

  @doc """
  Search presets by name or description.
  """
  def search_presets(query) do
    all_presets = get_all_presets()
    query_lower = String.downcase(query)

    Enum.filter(all_presets, fn {_id, preset} ->
      name_matches = String.contains?(String.downcase(preset.name), query_lower)
      desc_matches = String.contains?(String.downcase(preset.description), query_lower)
      name_matches or desc_matches
    end)
  end

  # Private helper functions

  defp validate_preset(preset_data) do
    required_fields = ["name", "description", "parameters"]

    case validate_required_fields(preset_data, required_fields) do
      :ok ->
        case validate_parameters(preset_data.parameters) do
          :ok -> {:ok, preset_data}
          {:error, reason} -> {:error, reason}
        end

      {:error, reason} ->
        {:error, reason}
    end
  end

  defp validate_required_fields(data, required_fields) do
    missing_fields = Enum.filter(required_fields, fn field ->
      not Map.has_key?(data, field)
    end)

    if Enum.empty?(missing_fields) do
      :ok
    else
      {:error, "Missing required fields: #{Enum.join(missing_fields, ", ")}"}
    end
  end

  defp validate_parameters(parameters) do
    if is_map(parameters) do
      :ok
    else
      {:error, "Parameters must be a map"}
    end
  end

  defp save_presets_to_file(presets) do
    # Ensure directory exists
    File.mkdir_p(Path.dirname(@presets_file))

    # Convert to JSON and save
    case Jason.encode(presets, pretty: true) do
      {:ok, json} ->
        case File.write(@presets_file, json) do
          :ok -> :ok
          {:error, reason} -> {:error, reason}
        end

      {:error, reason} ->
        {:error, "Failed to encode presets: #{reason}"}
    end
  end
end
