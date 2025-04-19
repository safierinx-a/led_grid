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

  @doc """
  Get detailed stats about the controller and buffer status.
  Used by the dashboard to display performance metrics.
  """
  def get_detailed_stats do
    GenServer.call(__MODULE__, :get_detailed_stats)
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
  def handle_call(:get_detailed_stats, _from, state) do
    # Get buffer status
    buffer_status = maybe_get_buffer_status()

    # Combine controller info with detailed stats
    stats = %{
      connected: state.connected,
      controller_count: length(state.connected_controllers),
      controllers: state.connected_controllers,
      buffer_status: buffer_status,
      detailed_stats: state.last_detailed_stats || %{}
    }

    # If we have detailed stats, broadcast them to refresh the UI
    if state.last_detailed_stats do
      # Add buffer status to the detailed stats
      detailed_stats = Map.put(state.last_detailed_stats, :buffer_status, buffer_status)
      broadcast_detailed_stats_update(detailed_stats)
    end

    {:reply, stats, state}
  end

  @impl true
  def handle_cast({:send_frame, frame}, state) do
    # Use the frame buffer instead of broadcasting directly
    if state.connected do
      # Send the frame to the buffer, passing the pattern ID if available
      pattern_id = if frame.metadata && Map.has_key?(frame.metadata, "pattern_id") do
        frame.metadata["pattern_id"]
      else
        nil
      end

      # Add to buffer - will be sent in batches
      Legrid.Controller.FrameBuffer.add_frame(frame, pattern_id: pattern_id)
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
    # Forward the frame to the buffer instead of broadcasting directly
    if state.connected do
      # Get pattern ID from metadata if available
      pattern_id = if frame.metadata && Map.has_key?(frame.metadata, "pattern_id") do
        frame.metadata["pattern_id"]
      else
        nil
      end

      # Add to buffer - will be sent in batches
      Legrid.Controller.FrameBuffer.add_frame(frame, pattern_id: pattern_id)
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

    # If we have a last frame, send it to the new controller as priority
    if new_state.last_frame do
      # Send directly as high priority to immediately show something
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:frame, new_state.last_frame})

      # Also flush the buffer to ensure consistent state
      Legrid.Controller.FrameBuffer.flush()
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
    new_state = %{state | last_stats_update: {controller_id, stats}}

    # Broadcast the stats update to the LiveView
    broadcast_stats_update(stats)

    {:noreply, new_state}
  end

  @impl true
  def handle_info({:display_sync, controller_id, sync_data}, state) do
    Logger.debug("Received display sync from controller #{controller_id}")

    # Store the buffer stats for dashboard access
    buffer_stats = sync_data["buffer_stats"] || %{}

    # Create a combined stats structure with both buffer stats and basic stats
    detailed_stats = %{
      buffer: buffer_stats,
      controller_id: controller_id,
      timestamp: DateTime.utc_now(),
      connected: true
    }

    # Store these stats for dashboard access
    new_state = %{state | last_detailed_stats: detailed_stats}

    # Broadcast the detailed stats update to the LiveView
    broadcast_detailed_stats_update(detailed_stats)

    {:noreply, new_state}
  end

  @impl true
  def handle_info(:request_detailed_stats, state) do
    if state.connected do
      # Request detailed stats from controllers
      Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:request_detailed_stats, nil})

      # If we have any detailed stats, broadcast them immediately too
      if state.last_detailed_stats do
        broadcast_detailed_stats_update(state.last_detailed_stats)
      end
    end

    {:noreply, state}
  end

  @impl true
  def handle_info({:batch_ready, controller_id, sequence, buffer_fullness, buffer_capacity}, state) do
    Logger.debug("Controller #{controller_id} processed batch ##{sequence}, buffer fullness: #{buffer_fullness}")

    # Signal to the frame buffer that a controller is ready for more frames
    try do
      Legrid.Controller.FrameBuffer.controller_ready(controller_id, sequence, buffer_fullness, buffer_capacity)
    rescue
      _ -> :ok # Silently handle if frame buffer module doesn't implement this yet
    end

    {:noreply, state}
  end

  @impl true
  def handle_info({:batch_requested, controller_id, last_sequence, space_available, urgent}, state) do
    Logger.debug("Controller #{controller_id} requested batch after sequence #{last_sequence}, space: #{space_available}, urgent: #{urgent}")

    # Signal to the frame buffer that a controller is requesting frames
    try do
      Legrid.Controller.FrameBuffer.handle_batch_request(controller_id, last_sequence, space_available, urgent)
    rescue
      e ->
        Logger.error("Error handling batch request: #{inspect(e)}")
        # Fall back to sending a frame directly if frame buffer doesn't support batch requests
        if state.last_frame do
          Phoenix.PubSub.broadcast(Legrid.PubSub, "controller:frames", {:frame, state.last_frame})
        end
    end

    {:noreply, state}
  end

  # Helper functions

  defp maybe_get_buffer_status do
    # Try to get buffer status if the module is available
    try do
      Legrid.Controller.FrameBuffer.status()
    rescue
      _ -> %{available: false}
    end
  end

  # Broadcast stats updates to LiveView components
  defp broadcast_stats_update(stats) do
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller_stats", {:controller_stats, stats})
  end

  # Broadcast detailed stats updates to LiveView components
  defp broadcast_detailed_stats_update(detailed_stats) do
    Phoenix.PubSub.broadcast(Legrid.PubSub, "controller_stats", {:controller_stats_detailed, detailed_stats})
  end
end
