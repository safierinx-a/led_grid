defmodule Legrid.Controller.Interface do
  @moduledoc """
  Interface for communicating with LED grid controllers.

  This module handles sending frames to the physical LED grid controller
  via websockets. It manages connection state and reconnection attempts.

  Note: This module now works with the ControllerChannel instead of making
  outbound WebSocket connections. Controllers connect to the server via
  the WebSocket channel.
  """

  use GenServer

  alias Legrid.Frame
  require Logger

  # Client API

  @doc """
  Starts the controller interface.

  Options:
  - width: Width of the LED grid
  - height: Height of the LED grid
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Send a frame to the controller.
  """
  def send_frame(%Frame{} = frame) do
    GenServer.cast(__MODULE__, {:send_frame, frame})
  end

  @doc """
  Get the current status of the controller connection.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  @doc """
  Request statistics from the controller.
  """
  def request_stats do
    GenServer.cast(__MODULE__, :request_stats)
  end

  @doc """
  Activate monitor mode - used when monitor view is active.
  Starts periodic stats collection.
  """
  def activate_monitor do
    GenServer.call(__MODULE__, {:set_monitor_active, true})
  end

  @doc """
  Deactivate monitor mode - used when monitor view is closed.
  Stops periodic stats collection.
  """
  def deactivate_monitor do
    GenServer.call(__MODULE__, {:set_monitor_active, false})
  end

  @doc """
  Send simulation configuration to the controller.
  """
  def send_simulation_config(options) do
    GenServer.cast(__MODULE__, {:send_simulation_config, options})
  end

  # Server callbacks

  @impl true
  def init(opts) do
    width = Keyword.get(opts, :width, 25)
    height = Keyword.get(opts, :height, 24)

    state = %{
      width: width,
      height: height,
      connected: false,
      last_frame: nil,
      last_stats_update: nil,
      last_detailed_stats: nil,
      monitor_active: false,  # Track if /monitor page is active
      connected_controllers: [],
      first_controller_joined: false
    }

    # Subscribe to frames and controller events
    Legrid.Patterns.Runner.subscribe()
    Phoenix.PubSub.subscribe(Legrid.PubSub, "controller:events")

    Logger.info("Controller Interface started - waiting for controllers to connect")

    {:ok, state}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      connected: state.connected,
      width: state.width,
      height: state.height,
      connected_controllers: state.connected_controllers
    }

    {:reply, status, state}
  end

  @impl true
  def handle_call({:set_monitor_active, active}, _from, state) do
    # When monitor page becomes active, immediately request detailed stats
    if active && !state.monitor_active do
      Process.send_after(self(), :request_detailed_stats, 100)
    end

    {:reply, :ok, %{state | monitor_active: active}}
  end

  @impl true
  def handle_cast({:send_frame, frame}, state) do
    # Broadcast the frame to all controllers via the PubSub system
    if state.connected do
      # Convert frame to format that can be sent
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:frame, frame})
    end

    # Always update last frame
    {:noreply, %{state | last_frame: frame}}
  end

  @impl true
  def handle_cast(:request_stats, state) do
    if state.connected do
      # Broadcast stats request to all controllers
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:request_stats, nil})
      Logger.info("Sending stats request to all controllers")
    end

    {:noreply, state}
  end

  @impl true
  def handle_cast({:send_simulation_config, options}, state) do
    if state.connected do
      # Broadcast simulation config to all controllers
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:simulation_config, options})
      Logger.info("Sending simulation config to all controllers: #{inspect(options)}")
    end

    {:noreply, state}
  end

  @impl true
  def handle_info({:frame, frame}, state) do
    # Forward the frame to all connected controllers
    if state.connected do
      # This broadcast will be received by the ControllerChannel
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:frame, frame})
    end

    {:noreply, %{state | last_frame: frame}}
  end

  @impl true
  def handle_info({:controller_joined, controller_id}, state) do
    Logger.info("Controller joined: #{controller_id}")

    # Update connected state and add controller to list
    new_state = %{state |
      connected: true,
      connected_controllers: [controller_id | state.connected_controllers],
      first_controller_joined: true
    }

    # If we have a last frame, send it to the new controller
    if new_state.last_frame do
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:frame, new_state.last_frame})
    end

    {:noreply, new_state}
  end

  @impl true
  def handle_info({:controller_left, controller_id}, state) do
    Logger.info("Controller left: #{controller_id}")

    # Remove the controller from our list
    updated_controllers = Enum.reject(state.connected_controllers, &(&1 == controller_id))

    # Update connected state - true if we still have any controllers
    new_state = %{state |
      connected: length(updated_controllers) > 0,
      connected_controllers: updated_controllers
    }

    {:noreply, new_state}
  end

  @impl true
  def handle_info({:stats_update, controller_id, stats}, state) do
    Logger.debug("Received stats from controller #{controller_id}: #{inspect(stats)}")

    # Store the stats update
    {:noreply, %{state | last_stats_update: {controller_id, stats}}}
  end

  @impl true
  def handle_info(:request_detailed_stats, state) do
    if state.connected do
      # Request detailed stats from controllers
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:request_detailed_stats, nil})
    end

    {:noreply, state}
  end
end
