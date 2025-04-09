FROM elixir:1.18-alpine as build

# Install build dependencies
RUN apk add --no-cache build-base npm git

WORKDIR /app

# Install hex + rebar
RUN mix local.hex --force && \
    mix local.rebar --force

# Set build ENV
ENV MIX_ENV=dev

# Install mix dependencies
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV

# Copy assets
COPY assets assets
COPY priv priv

# Install npm dependencies
RUN cd assets && npm install

# Copy config files
COPY config config

# Copy lib files
COPY lib lib

# Compile the project
RUN mix compile

# Expose port
EXPOSE 4000

CMD ["mix", "phx.server"] 