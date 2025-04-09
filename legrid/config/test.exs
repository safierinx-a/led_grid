import Config

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :legrid, LegridWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "427spTrdtrG1sM0aGaAHfyUvHBfUXRT3ZiX4Lidi6ZKzSDfc2WxphHio3sIt75Sx",
  server: false

# Print only warnings and errors during test
config :logger, level: :warning

# Initialize plugs at runtime for faster test compilation
config :phoenix, :plug_init_mode, :runtime

# Enable helpful, but potentially expensive runtime checks
config :phoenix_live_view,
  enable_expensive_runtime_checks: true
