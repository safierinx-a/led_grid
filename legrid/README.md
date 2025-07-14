# Legrid Server

A Phoenix-based server for LED grid pattern generation and controller management.

## Getting Started

To start the Legrid server:

```bash
# Install dependencies
mix deps.get

# Start Phoenix endpoint
mix phx.server
```

Now you can visit [`localhost:4000`](http://localhost:4000) from your browser to access the pattern dashboard.

## Controller Communication

The server automatically:

1. Accepts connections from LED grid controllers via WebSockets
2. Starts a default pattern (sine_field) when a controller connects
3. Processes batch acknowledgments from controllers
4. Manages sequence numbers for reliable delivery
5. Distributes frames to all connected controllers

## Batch Frame System

The server implements an efficient batch frame transmission system:

- Frames are collected and sent in batches for improved performance
- Dynamic batch sizing adjusts to pattern characteristics (6-60 frames per batch)
- Priority frames are sent immediately when patterns change
- Binary protocol minimizes bandwidth usage
- Controller acknowledgments ensure reliable delivery

Configuration in `config.exs`:

```elixir
config :legrid,
  batch_size: 60,                 # Max frames per regular batch
  priority_batch_size: 120,       # Max frames per priority batch
  batch_max_delay: 500,           # Max delay in ms before sending a partial batch
  batch_min_frames: 20            # Min frames before sending a partial batch
```

The batch frame system provides:

- Reduced WebSocket overhead
- Improved connection stability
- Better performance under network fluctuations
- Higher frame rates for smooth animations

## Pattern Management

The server includes multiple pattern generators:

- Sine fields
- Game of Life
- Plasma effects
- Clock displays
- Image renderers
- And more...

Patterns can be changed via the web interface or API.

## Development

During development:

- The server will automatically connect to any controllers that join
- A default pattern will start to immediately provide visual feedback
- Controller information and stats are logged for debugging

## Deployment

Ready to run in production? Please [check the Phoenix deployment guides](https://hexdocs.pm/phoenix/deployment.html).

## Learn more

- Official Phoenix website: https://www.phoenixframework.org/
- Guides: https://hexdocs.pm/phoenix/overview.html
- Docs: https://hexdocs.pm/phoenix
