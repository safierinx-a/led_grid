# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :legrid,
  generators: [timestamp_type: :utc_datetime],
  # Frame batch configuration
  batch_size: 120,                 # Max frames per batch
  batch_max_delay: 500,            # Max delay in ms before sending a partial batch
  batch_min_frames: 5,             # Min frames before sending a partial batch
  # Same-machine mode configuration
  same_machine_mode: false,         # Enable same-machine mode (no WebSocket)
  local_controller: [
    enabled: true,                  # Enable local controller
    led_pin: 18,                   # GPIO pin for LED data
    led_count: 600,                # Number of LEDs (25x24)
    width: 25,                     # Grid width
    height: 24,                    # Grid height
    controller_type: "python"      # "python" or "rust"
  ]

# Configures the endpoint
config :legrid, LegridWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: LegridWeb.ErrorHTML, json: LegridWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: Legrid.PubSub,
  live_view: [signing_salt: "C1aueHre"]

# Configure esbuild (the version is required)
config :esbuild,
  version: "0.17.11",
  default: [
    args:
      ~w(js/app.js --bundle --target=es2017 --outdir=../priv/static/assets --external:/fonts/* --external:/images/*),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => Path.expand("../deps", __DIR__)}
  ]

# Configure tailwind (the version is required)
config :tailwind,
  version: "3.4.3",
  default: [
    args: ~w(
      --config=tailwind.config.js
      --input=css/app.css
      --output=../priv/static/assets/app.css
    ),
    cd: Path.expand("../assets", __DIR__)
  ]

# Configures Elixir's Logger
config :logger, :console,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
