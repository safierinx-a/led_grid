defmodule LegridWeb.ApiController do
  use LegridWeb, :controller

  alias Legrid.Patterns.{Registry, Runner}
  alias Legrid.Controller.Interface

  def list_patterns(conn, _params) do
    patterns = Registry.list_patterns()
    json(conn, patterns)
  end

  def get_pattern(conn, %{"id" => id}) do
    case Registry.get_pattern(id) do
      {:ok, metadata} -> json(conn, metadata)
      {:error, :not_found} -> conn |> put_status(404) |> json(%{error: "Pattern not found"})
    end
  end

  def get_current_pattern(conn, _params) do
    case Runner.current_pattern() do
      {:ok, pattern} -> json(conn, pattern)
      {:error, _} -> conn |> put_status(404) |> json(%{error: "No pattern running"})
    end
  end

  def set_active_pattern(conn, %{"id" => id, "params" => params}) do
    case Registry.get_pattern(id) do
      {:ok, _metadata} ->
        Runner.start_pattern(id, params)
        json(conn, %{success: true})

      {:error, :not_found} ->
        conn |> put_status(404) |> json(%{error: "Pattern not found"})
    end
  end

  # Auto-preserve parameters when changing patterns
  def set_active_pattern(conn, %{"id" => id}) do
    # Get current pattern parameters if available
    current_params = case Runner.current_pattern() do
      {:ok, %{params: params}} when is_map(params) and map_size(params) > 0 -> params
      _ -> %{}
    end

    case Registry.get_pattern(id) do
      {:ok, metadata} ->
        # Ensure new pattern supports these parameters
        valid_params = current_params
        |> Enum.filter(fn {key, _} ->
          Map.has_key?(metadata.parameters, key)
        end)
        |> Enum.into(%{})

        Runner.start_pattern(id, valid_params)
        json(conn, %{success: true})

      {:error, :not_found} ->
        conn |> put_status(404) |> json(%{error: "Pattern not found"})
    end
  end

  def status(conn, _params) do
    controller_status = Interface.status()

    current_pattern = case Runner.current_pattern() do
      {:ok, pattern} -> pattern
      {:error, _} -> nil
    end

    status = %{
      controller: controller_status,
      current_pattern: current_pattern
    }

    json(conn, status)
  end
end
