# Legrid

To start your Phoenix server:

- Run `mix setup` to install and setup dependencies
- Start Phoenix endpoint with `mix phx.server` or inside IEx with `iex -S mix phx.server`

Now you can visit [`localhost:4000`](http://localhost:4000) from your browser.

Ready to run in production? Please [check our deployment guides](https://hexdocs.pm/phoenix/deployment.html).

## Batch Frame Transmission

This project implements a batch frame transmission system for improved performance and connection stability:

- Frames are collected and sent in batches of up to 120 frames
- Batch processing reduces WebSocket overhead and improves connection stability
- Pattern changes trigger immediate flushing of the current batch with priority
- Configuration in `config.exs`:
  ```elixir
  config :legrid,
    batch_size: 120,                 # Max frames per batch
    batch_max_delay: 500,            # Max delay in ms before sending a partial batch
    batch_min_frames: 5              # Min frames before sending a partial batch
  ```

The batch frame system works transparently with existing controllers and patterns, with no changes needed to pattern generators.

## Learn more

- Official website: https://www.phoenixframework.org/
- Guides: https://hexdocs.pm/phoenix/overview.html
- Docs: https://hexdocs.pm/phoenix
- Forum: https://elixirforum.com/c/phoenix-forum
- Source: https://github.com/phoenixframework/phoenix
