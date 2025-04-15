import Config

# Configure Legrid application settings
config :legrid,
  # No controller URL in production - waiting for controller to connect
  grid_width: 25,
  grid_height: 24

# For production, don't forget to configure the url host
# to something meaningful, Phoenix uses this information
# when generating URLs.
config :legrid, LegridWeb.Endpoint,
  url: [host: System.get_env("PHX_HOST", "example.com")],
  http: [port: String.to_integer(System.get_env("PORT", "4000"))],
  cache_static_manifest: "priv/static/cache_manifest.json"

# Do not print debug messages in production
config :logger, level: :info

# Runtime production configuration, including reading
# of environment variables, is done on config/runtime.exs.
