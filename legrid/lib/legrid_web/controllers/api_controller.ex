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

  def set_active_pattern(conn, %{"id" => id, "params" => params}) do
    case Registry.get_pattern(id) do
      {:ok, _metadata} ->
        Runner.start_pattern(id, params)
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
