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
  Clean up any resources used by the pattern generator.
  """
  @callback terminate(state :: map()) :: :ok

  @optional_callbacks [terminate: 1]
end
