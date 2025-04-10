defmodule Legrid.Patterns.Registry do
  @moduledoc """
  Registry for pattern generators.

  This module maintains a registry of all available pattern generators
  and provides functions to list, retrieve, and manage them.
  """

  use GenServer

  alias Legrid.Patterns.PatternBehaviour
  alias Legrid.Patterns.{SineWave, Lissajous, GameOfLife, PixelArt, OpticalIllusion, Clock, RadarSweep, PatternHelpers, ComplexPixelArt}

  # Client API

  @doc """
  Starts the pattern registry.
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Returns a list of all registered patterns with their metadata.
  """
  def list_patterns do
    GenServer.call(__MODULE__, :list_patterns)
  end

  @doc """
  Returns the metadata for a specific pattern.
  """
  def get_pattern(id) do
    GenServer.call(__MODULE__, {:get_pattern, id})
  end

  @doc """
  Registers a new pattern generator module.
  """
  def register_pattern(module) do
    GenServer.call(__MODULE__, {:register_pattern, module})
  end

  # Server callbacks

  @impl true
  def init(_opts) do
    patterns = discover_patterns()
    {:ok, %{patterns: patterns}}
  end

  @impl true
  def handle_call(:list_patterns, _from, state) do
    patterns = state.patterns
    |> Enum.map(fn {_id, module} -> module.metadata() end)

    {:reply, patterns, state}
  end

  @impl true
  def handle_call({:get_pattern, id}, _from, state) do
    case Map.get(state.patterns, id) do
      nil -> {:reply, {:error, :not_found}, state}
      module -> {:reply, {:ok, module.metadata()}, state}
    end
  end

  @impl true
  def handle_call({:register_pattern, module}, _from, state) do
    if implements_behaviour?(module, PatternBehaviour) do
      metadata = module.metadata()
      new_patterns = Map.put(state.patterns, metadata.id, module)
      {:reply, :ok, %{state | patterns: new_patterns}}
    else
      {:reply, {:error, :invalid_pattern}, state}
    end
  end

  # Helper functions

  defp discover_patterns do
    # Register our built-in patterns
    known_patterns = [SineWave, Lissajous, GameOfLife, PixelArt, OpticalIllusion, Clock, RadarSweep, ComplexPixelArt]

    Enum.reduce(known_patterns, %{}, fn module, acc ->
      if implements_behaviour?(module, PatternBehaviour) do
        metadata = module.metadata()
        Map.put(acc, metadata.id, module)
      else
        acc
      end
    end)
  end

  defp implements_behaviour?(module, behaviour) do
    behaviours = module.module_info(:attributes)
    |> Keyword.get(:behaviour, [])

    behaviour in behaviours
  end
end
