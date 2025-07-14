defmodule Legrid.Patterns.ParametricCurve do
  @moduledoc """
  Animated parametric curves: sine, rose, spiral, lemniscate, cardioid, butterfly, hypocycloid, clifford, and more.
  Each curve exposes its true mathematical parameters for maximum creative control.
  """

  @behaviour Legrid.Patterns.PatternBehaviour
  alias Legrid.Frame
  alias Legrid.Patterns.PatternHelpers

  @default_width 25
  @default_height 24

  @curve_types [
    "sine", "rose", "spiral", "lemniscate", "cardioid", "butterfly", "hypocycloid", "clifford"
  ]

  @impl true
  def metadata do
    %{
      id: "parametric_curve",
      name: "Parametric Curve",
      description: "A family of animated parametric curves and fields. Each curve exposes its true parameters.",
      parameters: %{
        "curve_type" => %{type: :enum, default: "sine", options: @curve_types, description: "Type of curve"},
        # Sine
        "amplitude" => %{type: :float, default: 0.5, min: 0.1, max: 1.0, description: "Wave amplitude (sine)"},
        "frequency" => %{type: :float, default: 1.0, min: 0.1, max: 5.0, description: "Wave frequency (sine)"},
        # Rose
        "n" => %{type: :integer, default: 4, min: 1, max: 12, description: "Numerator for k (rose curve)"},
        "d" => %{type: :integer, default: 1, min: 1, max: 12, description: "Denominator for k (rose curve)"},
        # Spiral
        "a" => %{type: :float, default: 1.0, min: 0.1, max: 2.0, description: "Spiral base radius (spiral, hypocycloid)"},
        "b" => %{type: :float, default: 0.2, min: 0.0, max: 1.0, description: "Spiral/hypocycloid growth (spiral, hypocycloid)"},
        # Butterfly
        "butterfly_scale" => %{type: :float, default: 1.0, min: 0.1, max: 3.0, description: "Butterfly curve scale"},
        "butterfly_t_range" => %{type: :float, default: 12.0, min: 2.0, max: 24.0, description: "Butterfly t range (π units)"},
        # Hypocycloid
        "hypo_a" => %{type: :float, default: 5.0, min: 1.0, max: 20.0, description: "a parameter (hypocycloid)"},
        "hypo_b" => %{type: :float, default: 3.0, min: 0.5, max: 10.0, description: "b parameter (hypocycloid)"},
        # Clifford attractor
        "cliff_a" => %{type: :float, default: 1.4, min: -2.0, max: 2.0, description: "a parameter (clifford)"},
        "cliff_b" => %{type: :float, default: -1.6, min: -2.0, max: 2.0, description: "b parameter (clifford)"},
        "cliff_c" => %{type: :float, default: 1.0, min: -2.0, max: 2.0, description: "c parameter (clifford)"},
        "cliff_d" => %{type: :float, default: 0.7, min: -2.0, max: 2.0, description: "d parameter (clifford)"},
        "cliff_iters" => %{type: :integer, default: 100, min: 10, max: 1000, description: "Iterations (clifford)"},
        # Global
        "brightness" => %{type: :float, default: 1.0, min: 0.1, max: 1.0, description: "Overall brightness"},
        "color_scheme" => %{type: :enum, default: "enhanced_rainbow", options: Map.keys(PatternHelpers.color_schemes()), description: "Color scheme"},
        "speed" => %{type: :float, default: 0.5, min: 0.1, max: 2.0, description: "Animation speed"}
      },
      visible_parameters: %{
        "sine" => ["curve_type", "amplitude", "frequency", "brightness", "color_scheme", "speed"],
        "rose" => ["curve_type", "n", "d", "brightness", "color_scheme", "speed"],
        "spiral" => ["curve_type", "a", "b", "brightness", "color_scheme", "speed"],
        "lemniscate" => ["curve_type", "brightness", "color_scheme", "speed"],
        "cardioid" => ["curve_type", "brightness", "color_scheme", "speed"],
        "butterfly" => ["curve_type", "butterfly_scale", "butterfly_t_range", "brightness", "color_scheme", "speed"],
        "hypocycloid" => ["curve_type", "a", "b", "hypo_a", "hypo_b", "brightness", "color_scheme", "speed"],
        "clifford" => ["curve_type", "cliff_a", "cliff_b", "cliff_c", "cliff_d", "cliff_iters", "brightness", "color_scheme", "speed"]
      }
    }
  end

  @impl true
  def init(params) do
    state = %{
      width: @default_width,
      height: @default_height,
      curve_type: PatternHelpers.get_param(params, "curve_type", "sine", :string),
      amplitude: PatternHelpers.get_param(params, "amplitude", 0.5, :float),
      frequency: PatternHelpers.get_param(params, "frequency", 1.0, :float),
      n: PatternHelpers.get_param(params, "n", 4, :integer),
      d: PatternHelpers.get_param(params, "d", 1, :integer),
      a: PatternHelpers.get_param(params, "a", 1.0, :float),
      b: PatternHelpers.get_param(params, "b", 0.2, :float),
      butterfly_scale: PatternHelpers.get_param(params, "butterfly_scale", 1.0, :float),
      butterfly_t_range: PatternHelpers.get_param(params, "butterfly_t_range", 12.0, :float),
      hypo_a: PatternHelpers.get_param(params, "hypo_a", 5.0, :float),
      hypo_b: PatternHelpers.get_param(params, "hypo_b", 3.0, :float),
      cliff_a: PatternHelpers.get_param(params, "cliff_a", 1.4, :float),
      cliff_b: PatternHelpers.get_param(params, "cliff_b", -1.6, :float),
      cliff_c: PatternHelpers.get_param(params, "cliff_c", 1.0, :float),
      cliff_d: PatternHelpers.get_param(params, "cliff_d", 0.7, :float),
      cliff_iters: PatternHelpers.get_param(params, "cliff_iters", 100, :integer),
      brightness: PatternHelpers.get_param(params, "brightness", 1.0, :float),
      color_scheme: PatternHelpers.get_param(params, "color_scheme", "enhanced_rainbow", :string),
      speed: PatternHelpers.get_param(params, "speed", 0.5, :float),
      time: 0.0
    }
    {:ok, state}
  end

  @curve_functions %{
    "sine" => &__MODULE__.curve_sine/5,
    "rose" => &__MODULE__.curve_rose/5,
    "spiral" => &__MODULE__.curve_spiral/5,
    "lemniscate" => &__MODULE__.curve_lemniscate/5,
    "cardioid" => &__MODULE__.curve_cardioid/5,
    "butterfly" => &__MODULE__.curve_butterfly/5,
    "hypocycloid" => &__MODULE__.curve_hypocycloid/5,
    "clifford" => &__MODULE__.curve_clifford/5
  }

  @impl true
  def render(state, elapsed_ms) do
    t = state.time + elapsed_ms / 1000.0
    curve_fn = Map.get(@curve_functions, state.curve_type, &__MODULE__.curve_sine/5)

    pixels = for y <- 0..(state.height-1), x <- 0..(state.width-1) do
      value = curve_fn.(x, y, t, state, state)
      PatternHelpers.get_color(state.color_scheme, value, state.brightness)
    end

    frame = Frame.new("parametric_curve", state.width, state.height, pixels)
    {:ok, frame, %{state | time: t}}
  end

  @impl true
  def update_params(state, params) do
    updated_state = PatternHelpers.apply_global_params(state, params)
    updated_state = %{updated_state |
      curve_type: PatternHelpers.get_param(params, "curve_type", state.curve_type, :string),
      amplitude: PatternHelpers.get_param(params, "amplitude", state.amplitude, :float),
      frequency: PatternHelpers.get_param(params, "frequency", state.frequency, :float),
      n: PatternHelpers.get_param(params, "n", state.n, :integer),
      d: PatternHelpers.get_param(params, "d", state.d, :integer),
      a: PatternHelpers.get_param(params, "a", state.a, :float),
      b: PatternHelpers.get_param(params, "b", state.b, :float),
      butterfly_scale: PatternHelpers.get_param(params, "butterfly_scale", state.butterfly_scale, :float),
      butterfly_t_range: PatternHelpers.get_param(params, "butterfly_t_range", state.butterfly_t_range, :float),
      hypo_a: PatternHelpers.get_param(params, "hypo_a", state.hypo_a, :float),
      hypo_b: PatternHelpers.get_param(params, "hypo_b", state.hypo_b, :float),
      cliff_a: PatternHelpers.get_param(params, "cliff_a", state.cliff_a, :float),
      cliff_b: PatternHelpers.get_param(params, "cliff_b", state.cliff_b, :float),
      cliff_c: PatternHelpers.get_param(params, "cliff_c", state.cliff_c, :float),
      cliff_d: PatternHelpers.get_param(params, "cliff_d", state.cliff_d, :float),
      cliff_iters: PatternHelpers.get_param(params, "cliff_iters", state.cliff_iters, :integer)
    }
    {:ok, updated_state}
  end

  # 1D moving sine wave (horizontal)
  def curve_sine(x, y, t, state, _params) do
    y_center = state.height / 2
    amplitude = state.amplitude * (state.height / 2)
    frequency = state.frequency
    phase = t * state.speed * 2 * :math.pi
    wave = y_center + amplitude * :math.sin((x / state.width) * 2 * :math.pi * frequency + phase)
    dist = abs(y - wave)
    value = :math.exp(-dist * 1.5)
    value
  end

  # Rose curve: k = n/d
  def curve_rose(x, y, t, state, _params) do
    n = state.n
    d = state.d
    k = n / d
    cx = state.width / 2
    cy = state.height / 2
    dx = x - cx
    dy = y - cy
    theta = :math.atan2(dy, dx)
    r = :math.sqrt(dx*dx + dy*dy)
    rose = :math.cos(k * theta + t * state.speed)
    max_r = min(cx, cy) * 0.9
    curve_r = max_r * (0.5 + 0.5 * rose)
    dist = abs(r - curve_r)
    value = :math.exp(-dist * 2.0)
    value
  end

  # Spiral: r = a + bθ
  def curve_spiral(x, y, t, state, _params) do
    a = state.a * min(state.width, state.height) / 6
    b = state.b * min(state.width, state.height) / 6
    cx = state.width / 2
    cy = state.height / 2
    dx = x - cx
    dy = y - cy
    theta = :math.atan2(dy, dx) + t * state.speed
    r = :math.sqrt(dx*dx + dy*dy)
    spiral_r = a + b * theta
    dist = abs(r - spiral_r)
    value = :math.exp(-dist * 2.0)
    value
  end

  # Lemniscate of Bernoulli: r^2 = a^2 cos(2θ)
  def curve_lemniscate(x, y, t, state, _params) do
    a = min(state.width, state.height) / 3
    cx = state.width / 2
    cy = state.height / 2
    dx = x - cx
    dy = y - cy
    theta = :math.atan2(dy, dx) + t * state.speed
    r = :math.sqrt(dx*dx + dy*dy)
    lem_r = :math.sqrt(abs(a * a * :math.cos(2 * theta)))
    dist = abs(r - lem_r)
    value = :math.exp(-dist * 2.0)
    value
  end

  # Cardioid: r = a(1 + cosθ)
  def curve_cardioid(x, y, t, state, _params) do
    a = min(state.width, state.height) / 4
    cx = state.width / 2
    cy = state.height / 2
    dx = x - cx
    dy = y - cy
    theta = :math.atan2(dy, dx) + t * state.speed
    r = :math.sqrt(dx*dx + dy*dy)
    card_r = a * (1 + :math.cos(theta))
    dist = abs(r - card_r)
    value = :math.exp(-dist * 2.0)
    value
  end

  # Butterfly curve: parametric, t in [0, butterfly_t_range * pi]
  def curve_butterfly(x, y, t, state, _params) do
    scale = state.butterfly_scale * min(state.width, state.height) / 6
    t_range = state.butterfly_t_range * :math.pi
    cx = state.width / 2
    cy = state.height / 2
    # Find closest t for this (x, y)
    min_dist = Enum.reduce(0..200, 1.0e6, fn i, acc ->
      tt = i / 200 * t_range + t * state.speed
      bx = :math.sin(tt) * (:math.exp(:math.cos(tt)) - 2 * :math.cos(4 * tt) - :math.pow(:math.sin(tt / 12), 5)) * scale + cx
      by = :math.cos(tt) * (:math.exp(:math.cos(tt)) - 2 * :math.cos(4 * tt) - :math.pow(:math.sin(tt / 12), 5)) * scale + cy
      dist = :math.sqrt((x - bx) * (x - bx) + (y - by) * (y - by))
      if dist < acc, do: dist, else: acc
    end)
    value = :math.exp(-min_dist * 2.0)
    value
  end

  # Hypocycloid: x = (a-b)cos(t) + bcos((a-b)/b t), y = (a-b)sin(t) - bsin((a-b)/b t)
  def curve_hypocycloid(x, y, t, state, _params) do
    a = state.hypo_a * min(state.width, state.height) / 10
    b = state.hypo_b * min(state.width, state.height) / 10
    cx = state.width / 2
    cy = state.height / 2
    t_range = 2 * :math.pi
    min_dist = Enum.reduce(0..200, 1.0e6, fn i, acc ->
      tt = i / 200 * t_range + t * state.speed
      hx = (a - b) * :math.cos(tt) + b * :math.cos((a - b) / b * tt) + cx
      hy = (a - b) * :math.sin(tt) - b * :math.sin((a - b) / b * tt) + cy
      dist = :math.sqrt((x - hx) * (x - hx) + (y - hy) * (y - hy))
      if dist < acc, do: dist, else: acc
    end)
    value = :math.exp(-min_dist * 2.0)
    value
  end

  # Clifford attractor: x_{n+1} = sin(a y_n) + c cos(a x_n), y_{n+1} = sin(b x_n) + d cos(b y_n)
  def curve_clifford(x, y, t, state, _params) do
    a = state.cliff_a
    b = state.cliff_b
    c = state.cliff_c
    d = state.cliff_d
    iters = state.cliff_iters
    cx = state.width / 2
    cy = state.height / 2
    # Map (x, y) to [-2, 2]
    x0 = 4 * (x / state.width - 0.5)
    y0 = 4 * (y / state.height - 0.5)
    {xn, yn} = Enum.reduce(1..iters, {x0, y0}, fn _, {xi, yi} ->
      {
        :math.sin(a * yi) + c * :math.cos(a * xi),
        :math.sin(b * xi) + d * :math.cos(b * yi)
      }
    end)
    # Map result back to grid
    dist = :math.sqrt((x0 - xn) * (x0 - xn) + (y0 - yn) * (y0 - yn))
    value = :math.exp(-dist * 2.0)
    value
  end
end
