defmodule Legrid.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    # Get configuration
    controller_url = Application.get_env(:legrid, :controller_url, "ws://localhost:8080")
    grid_width = Application.get_env(:legrid, :grid_width, 25)
    grid_height = Application.get_env(:legrid, :grid_height, 24)
    batch_size = Application.get_env(:legrid, :batch_size, 120)

    children = [
      # Start the Telemetry supervisor
      LegridWeb.Telemetry,
      # Start the PubSub system
      {Phoenix.PubSub, name: Legrid.PubSub},
      # Start the Pattern Registry
      {Legrid.Patterns.Registry, []},
      # Start the Pattern Runner
      {Legrid.Patterns.Runner, []},
      # Start the Frame Buffer for batch transmission
      {Legrid.Controller.FrameBuffer, [
        batch_size: batch_size,
        max_delay: 500,  # 500ms max before sending partial batch
        min_frames: 5    # At least 5 frames before sending partial batch
      ]},
      # Start the Controller Interface
      {Legrid.Controller.Interface, [
        url: controller_url,
        width: grid_width,
        height: grid_height
      ]},
      # Start Finch
      {Finch, name: Legrid.Finch},
      # Start the Endpoint (http/https)
      LegridWeb.Endpoint
      # Start a worker by calling: Legrid.Worker.start_link(arg)
      # {Legrid.Worker, arg}
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Legrid.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    LegridWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
