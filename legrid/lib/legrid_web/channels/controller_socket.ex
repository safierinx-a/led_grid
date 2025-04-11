defmodule LegridWeb.ControllerSocket do
  @moduledoc """
  Socket for hardware controllers to connect to.

  This socket allows Raspberry Pi and other hardware controllers
  to connect to the Legrid server and receive frames.
  """

  use Phoenix.Socket

  ## Channels
  channel "controller:*", LegridWeb.ControllerChannel

  @impl true
  def connect(_params, socket, _connect_info) do
    # Accept all connections for now
    # In production, you might want to add authentication
    {:ok, socket}
  end

  @impl true
  def id(_socket), do: nil
end
