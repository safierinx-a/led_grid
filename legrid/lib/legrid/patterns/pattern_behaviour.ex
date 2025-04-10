defmodule Legrid.Patterns.PatternBehaviour do
  @moduledoc """
  Defines the behaviour that all pattern generators must implement.

  A pattern generator is responsible for creating frames of animation
  for the LED grid based on its specific algorithm and parameters.
  """

  alias Legrid.Frame

  @doc """
  Returns the metadata for this pattern generator.

  The metadata includes:
  - id: Unique identifier for this pattern
  - name: Human-readable name
  - description: Brief explanation of what the pattern does
  - parameters: Map of parameter names to parameter definitions

  Each pattern should support the following global parameters:
  - "brightness": Overall brightness adjustment (0.0-1.0)
  - "color_scheme": Color scheme to use (e.g., "rainbow", "mono", "complementary")
  - "speed": General speed control for the pattern animation
  """
  @callback metadata() :: %{
    id: String.t(),
    name: String.t(),
    description: String.t(),
    parameters: %{required(String.t()) => %{
      type: :integer | :float | :boolean | :string | :color | :enum,
      default: any(),
      min: number() | nil,
      max: number() | nil,
      options: list() | nil,
      description: String.t()
    }}
  }

  @doc """
  Initialize the pattern generator with the given parameters.

  Returns a state map that will be passed to the `render/2` function.
  """
  @callback init(params :: map()) :: {:ok, state :: map()} | {:error, reason :: String.t()}

  @doc """
  Generate a new frame based on the current state and elapsed time.

  - state: The current state of the pattern generator
  - elapsed_ms: Time elapsed since the last frame in milliseconds

  Returns a tuple containing the new frame and the updated state.
  """
  @callback render(state :: map(), elapsed_ms :: non_neg_integer()) ::
    {:ok, frame :: Frame.t(), new_state :: map()} |
    {:error, reason :: String.t()}

  @doc """
  Update pattern parameters during runtime.

  This function allows for real-time parameter adjustments while the pattern is running.
  It should update the parameters in the state while preserving any animation context.

  - state: The current state of the pattern generator
  - params: New parameter values to apply

  Returns an updated state to be used for future render calls.
  """
  @callback update_params(state :: map(), params :: map()) ::
    {:ok, new_state :: map()} |
    {:error, reason :: String.t()}

  @doc """
  Clean up any resources used by the pattern generator.
  """
  @callback terminate(state :: map()) :: :ok

  @optional_callbacks [terminate: 1]
end
