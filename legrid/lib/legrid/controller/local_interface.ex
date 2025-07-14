defmodule Legrid.Controller.LocalInterface do
  @moduledoc """
  Local interface for same-machine LED control.

  This module replaces the WebSocket-based communication with direct
  inter-process communication for same-machine deployments.
  """

  use GenServer
  require Logger

  alias Legrid.Frame

  # Client API

  @doc """
  Starts the local controller interface.
  """
  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Send a frame directly to the local LED controller.
  """
  def send_frame(%Frame{} = frame) do
    GenServer.cast(__MODULE__, {:send_frame, frame})
  end

  @doc """
  Get the current status of the local controller.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  @doc """
  Start the local LED controller process.
  """
  def start_local_controller do
    GenServer.call(__MODULE__, :start_local_controller)
  end

  @doc """
  Stop the local LED controller process.
  """
  def stop_local_controller do
    GenServer.call(__MODULE__, :stop_local_controller)
  end

  # Server callbacks

  @impl true
  def init(opts) do
    width = Keyword.get(opts, :width, 25)
    height = Keyword.get(opts, :height, 24)
    led_pin = Keyword.get(opts, :led_pin, 18)
    led_count = Keyword.get(opts, :led_count, width * height)

    state = %{
      width: width,
      height: height,
      led_pin: led_pin,
      led_count: led_count,
      connected: false,
      local_controller_pid: nil,
      last_frame: nil,
      frame_count: 0,
      last_frame_time: nil,
      fps: 0.0
    }

    # Subscribe to frame updates from pattern runner
    Legrid.Patterns.Runner.subscribe()

    Logger.info("Local Controller Interface started")

    {:ok, state}
  end

  @impl true
  def handle_call(:status, _from, state) do
    status = %{
      connected: state.connected,
      width: state.width,
      height: state.height,
      led_pin: state.led_pin,
      led_count: state.led_count,
      fps: state.fps,
      frame_count: state.frame_count
    }

    {:reply, status, state}
  end

  @impl true
  def handle_call(:start_local_controller, _from, state) do
    case start_local_controller_process(state) do
      {:ok, pid} ->
        Logger.info("Local LED controller started with PID: #{inspect(pid)}")
        {:reply, {:ok, pid}, %{state | connected: true, local_controller_pid: pid}}

      {:error, reason} ->
        Logger.error("Failed to start local LED controller: #{inspect(reason)}")
        {:reply, {:error, reason}, state}
    end
  end

  @impl true
  def handle_call(:stop_local_controller, _from, state) do
    case stop_local_controller_process(state.local_controller_pid) do
      :ok ->
        Logger.info("Local LED controller stopped")
        {:reply, :ok, %{state | connected: false, local_controller_pid: nil}}

      {:error, reason} ->
        Logger.error("Failed to stop local LED controller: #{inspect(reason)}")
        {:reply, {:error, reason}, state}
    end
  end

  @impl true
  def handle_cast({:send_frame, frame}, state) do
    if state.connected and state.local_controller_pid do
      # Send frame directly to local controller
      send(state.local_controller_pid, {:frame, frame})

      # Update statistics
      current_time = System.monotonic_time(:millisecond)
      new_fps = calculate_fps(current_time, state.last_frame_time, state.fps)

      new_state = %{state |
        last_frame: frame,
        frame_count: state.frame_count + 1,
        last_frame_time: current_time,
        fps: new_fps
      }

      {:noreply, new_state}
    else
      {:noreply, state}
    end
  end

  @impl true
  def handle_info({:frame, frame}, state) do
    # Forward frame from pattern runner to local controller
    send_frame(frame)
    {:noreply, state}
  end

  @impl true
  def handle_info({:controller_stats, stats}, state) do
    Logger.debug("Received stats from local controller: #{inspect(stats)}")
    {:noreply, state}
  end

  # Private functions

  defp start_local_controller_process(state) do
    # Start the local LED controller as a separate process
    # This could be a Python process via Port or a Rust process
    case start_python_controller(state) do
      {:ok, pid} -> {:ok, pid}
      {:error, _} -> start_rust_controller(state)
    end
  end

  defp start_python_controller(state) do
    # Start Python controller via Port
    python_script = Path.join([:code.priv_dir(:legrid), "scripts", "local_controller.py"])

    if File.exists?(python_script) do
      port = Port.open({:spawn, "python3 #{python_script} --width #{state.width} --height #{state.height} --led-pin #{state.led_pin}"}, [
        {:packet, 4},
        :binary,
        :exit_status
      ])

      # Send initial configuration
      config = %{
        width: state.width,
        height: state.height,
        led_pin: state.led_pin,
        led_count: state.led_count
      }

      Port.command(port, :erlang.term_to_binary(config))

      {:ok, port}
    else
      {:error, :python_script_not_found}
    end
  end

  defp start_rust_controller(state) do
    # Start Rust controller via Port
    rust_binary = Path.join([:code.priv_dir(:legrid), "bin", "local_controller"])

    if File.exists?(rust_binary) do
      port = Port.open({:spawn, "#{rust_binary} --width #{state.width} --height #{state.height} --led-pin #{state.led_pin}"}, [
        {:packet, 4},
        :binary,
        :exit_status
      ])

      {:ok, port}
    else
      {:error, :rust_binary_not_found}
    end
  end

  defp stop_local_controller_process(pid) when is_pid(pid) do
    Process.exit(pid, :normal)
    :ok
  end

  defp stop_local_controller_process(port) when is_port(port) do
    Port.close(port)
    :ok
  end

  defp stop_local_controller_process(_), do: {:error, :invalid_pid}

  defp calculate_fps(current_time, last_time, current_fps) do
    case last_time do
      nil -> current_fps
      last ->
        delta = (current_time - last) / 1000.0
        if delta > 0 do
          instant_fps = 1.0 / delta
          current_fps * 0.8 + instant_fps * 0.2
        else
          current_fps
        end
    end
  end
end
