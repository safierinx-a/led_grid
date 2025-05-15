%
% LED Grid Controller for AtomVM
%
-module(led_controller).
-export([start/0]).

% Configuration
-define(SSID, "vasant_six_three_2.4G").
-define(PASSWORD, "invideo_ai_123").
-define(SERVER_HOST, "192.168.1.11").
-define(SERVER_PORT, 4000).
-define(SERVER_PATH, "/controller/websocket").

-define(LED_COUNT, 600).
-define(LED_PIN, 5).
-define(GRID_WIDTH, 25).
-define(GRID_HEIGHT, 24).
-define(SERPENTINE_LAYOUT, true).

% Statistics
-record(stats, {
    frame_count = 0,
    last_frame_time = 0,
    current_fps = 0.0,
    connection_drops = 0
}).

% Main entry point
start() ->
    io:format("LED Grid Controller starting...~n"),
    
    % Initialize hardware
    ok = init_hardware(),
    
    % Test LEDs
    test_leds(),
    
    % Connect to WiFi
    {ok, _} = wifi:start(),
    io:format("Connecting to WiFi...~n"),
    ok = wifi:connect(?SSID, ?PASSWORD),
    {ok, Info} = wifi:get_sta_info(),
    IpAddr = proplists:get_value(ip, Info),
    io:format("WiFi connected. IP: ~p~n", [IpAddr]),
    
    % Initialize WebSocket connection
    connect_websocket().

% Initialize LED hardware
init_hardware() ->
    % Initialize NeoPixel strip through ESP-IDF
    neopixel:init(?LED_PIN, ?LED_COUNT),
    io:format("LED hardware initialized~n"),
    ok.

% Test LED function
test_leds() ->
    io:format("Starting LED test pattern...~n"),
    
    % Clear all LEDs
    clear_leds(),
    timer:sleep(1000),
    
    % Red test
    io:format("TEST: Setting RED pixels (255 brightness)~n"),
    [neopixel:set_pixel(I, {255, 0, 0}) || I <- lists:seq(0, min(49, ?LED_COUNT-1))],
    neopixel:show(),
    timer:sleep(3000),
    
    % Green test
    io:format("TEST: Setting GREEN pixels (255 brightness)~n"),
    [neopixel:set_pixel(I, {0, 255, 0}) || I <- lists:seq(0, min(49, ?LED_COUNT-1))],
    neopixel:show(),
    timer:sleep(3000),
    
    % Blue test
    io:format("TEST: Setting BLUE pixels (255 brightness)~n"),
    [neopixel:set_pixel(I, {0, 0, 255}) || I <- lists:seq(0, min(49, ?LED_COUNT-1))],
    neopixel:show(),
    timer:sleep(3000),
    
    % White test
    io:format("TEST: Setting WHITE pixels (255 brightness)~n"),
    [neopixel:set_pixel(I, {255, 255, 255}) || I <- lists:seq(0, min(49, ?LED_COUNT-1))],
    neopixel:show(),
    timer:sleep(3000),
    
    % Clear all LEDs
    clear_leds(),
    io:format("Test pattern completed~n"),
    ok.

% Test GPIO function
test_gpio() ->
    io:format("Starting GPIO pin test...~n"),
    TestPin = ?LED_PIN,
    
    gpio:set_direction(TestPin, output),
    
    % Blink 10 times
    [begin
        io:format("GPIO HIGH~n"),
        gpio:digital_write(TestPin, high),
        timer:sleep(500),
        io:format("GPIO LOW~n"),
        gpio:digital_write(TestPin, low),
        timer:sleep(500)
     end || _ <- lists:seq(1, 10)],
    
    io:format("GPIO test completed~n"),
    ok.

% Clear all LEDs
clear_leds() ->
    [neopixel:set_pixel(I, {0, 0, 0}) || I <- lists:seq(0, ?LED_COUNT-1)],
    neopixel:show().

% Connect WebSocket and handle messages
connect_websocket() ->
    Controller = self(),
    Pid = spawn(fun() -> websocket_client(Controller) end),
    websocket_loop(Pid, #stats{}).

websocket_client(Controller) ->
    % Generate controller ID
    {ok, MAC} = wifi:get_mac(),
    ControllerId = lists:flatten(io_lib:format("esp32-~2.16.0B~2.16.0B~2.16.0B~2.16.0B~2.16.0B~2.16.0B", 
                                             MAC)),
    
    % Connect to Phoenix server
    WSUrl = lists:flatten(io_lib:format("ws://~s:~p~s", 
                         [?SERVER_HOST, ?SERVER_PORT, ?SERVER_PATH])),
    io:format("WebSocket connecting to: ~s~n", [WSUrl]),
    
    % Initialize websocket client
    {ok, WS} = websocket:open(WSUrl),
    
    % Join Phoenix channel
    JoinMsg = #{
        topic => <<"controller:lobby">>,
        event => <<"phx_join">>,
        ref => <<"1">>,
        payload => #{
            controller_id => list_to_binary(ControllerId)
        }
    },
    ok = websocket:send(WS, {text, jsx:encode(JoinMsg)}),
    io:format("Sent join message~n"),
    
    % Send controller info
    InfoMsg = #{
        topic => <<"controller:lobby">>,
        event => <<"stats">>,
        ref => null,
        payload => #{
            type => <<"controller_info">>,
            id => list_to_binary(ControllerId),
            width => ?GRID_WIDTH,
            height => ?GRID_HEIGHT,
            version => <<"1.0.0">>,
            hardware => <<"ESP32-AtomVM">>,
            layout => <<"serpentine">>,
            orientation => #{
                flip_x => false,
                flip_y => false,
                transpose => false
            }
        }
    },
    ok = websocket:send(WS, {text, jsx:encode(InfoMsg)}),
    io:format("Sent controller info~n"),
    
    % Start heartbeat timer
    erlang:send_after(30000, self(), heartbeat),
    
    % Enter websocket receive loop
    websocket_receive_loop(WS, Controller, ControllerId).

websocket_receive_loop(WS, Controller, ControllerId) ->
    receive
        heartbeat ->
            HeartbeatMsg = #{
                topic => <<"phoenix">>,
                event => <<"heartbeat">>,
                payload => #{},
                ref => list_to_binary(integer_to_list(erlang:system_time(millisecond)))
            },
            websocket:send(WS, {text, jsx:encode(HeartbeatMsg)}),
            io:format("Sent heartbeat~n"),
            erlang:send_after(30000, self(), heartbeat),
            websocket_receive_loop(WS, Controller, ControllerId);
            
        {websocket, WS, {text, Msg}} ->
            io:format("Text message received: ~p~n", [Msg]),
            DecodedMsg = jsx:decode(Msg, [return_maps]),
            handle_text_message(DecodedMsg, WS, ControllerId),
            websocket_receive_loop(WS, Controller, ControllerId);
            
        {websocket, WS, {binary, Payload}} ->
            Controller ! {binary_frame, Payload},
            websocket_receive_loop(WS, Controller, ControllerId);
            
        {websocket, WS, closed} ->
            io:format("WebSocket disconnected~n"),
            Controller ! {connection_closed},
            timer:sleep(5000),
            connect_websocket()
    end.

handle_text_message(#{<<"event">> := <<"phx_reply">>} = Msg, _WS, _ControllerId) ->
    Status = maps:get(<<"status">>, maps:get(<<"payload">>, Msg)),
    case Status of
        <<"ok">> ->
            io:format("Channel join successful~n");
        _ ->
            io:format("Channel join failed~n")
    end;

handle_text_message(#{<<"event">> := <<"ping">>} = _Msg, WS, _ControllerId) ->
    PongMsg = #{
        topic => <<"controller:lobby">>,
        event => <<"pong">>,
        payload => #{},
        ref => null
    },
    websocket:send(WS, {text, jsx:encode(PongMsg)}),
    io:format("Sent pong~n");

handle_text_message(#{<<"event">> := <<"request_stats">>} = _Msg, WS, ControllerId) ->
    StatsMsg = #{
        topic => <<"controller:lobby">>,
        event => <<"stats">>,
        ref => null,
        payload => #{
            frames_received => 0, % TODO: Get from stats
            frames_displayed => 0,
            connection_drops => 0,
            fps => 0.0,
            connection_uptime => erlang:system_time(second),
            timestamp => erlang:system_time(millisecond)
        }
    },
    websocket:send(WS, {text, jsx:encode(StatsMsg)}),
    io:format("Sent stats~n");

handle_text_message(_Msg, _WS, _ControllerId) ->
    ok.

% Main loop for processing frames and updating stats
websocket_loop(WebSocketPid, Stats) ->
    receive
        {binary_frame, Payload} ->
            % Process binary frame
            NewStats = handle_binary_frame(Payload, Stats),
            websocket_loop(WebSocketPid, NewStats);
            
        {connection_closed} ->
            % Update connection drops
            NewStats = Stats#stats{connection_drops = Stats#stats.connection_drops + 1},
            websocket_loop(WebSocketPid, NewStats)
    end.

% Handle binary frame data
handle_binary_frame(Payload, Stats) ->
    % Extract header information
    <<Version:8, Type:8, _FrameId:32, Width:16/little, Height:16/little, PixelData/binary>> = Payload,
    
    % Only handle full frames (type 1)
    case Type of
        1 ->
            % Calculate FPS
            CurrentTime = erlang:system_time(millisecond),
            CurrentFps = case Stats#stats.last_frame_time of
                0 -> 
                    0.0;
                LastTime ->
                    DeltaTime = (CurrentTime - LastTime) / 1000.0,
                    case DeltaTime > 0 of
                        true ->
                            InstantFps = 1.0 / DeltaTime,
                            Stats#stats.current_fps * 0.8 + InstantFps * 0.2;
                        false ->
                            Stats#stats.current_fps
                    end
            end,
            
            % Update LED strip
            process_pixel_data(PixelData),
            
            % Update stats
            Stats#stats{
                frame_count = Stats#stats.frame_count + 1,
                last_frame_time = CurrentTime,
                current_fps = CurrentFps
            };
        _ ->
            io:format("Unsupported frame type: ~p~n", [Type]),
            Stats
    end.

% Process pixel data and update LEDs
process_pixel_data(PixelData) ->
    PixelCount = min(byte_size(PixelData) div 3, ?LED_COUNT),
    LitPixels = process_pixels(PixelData, 0, 0),
    
    % Show the updated pixels
    neopixel:show(),
    
    % Log status
    io:format("Frame displayed: ~p/~p pixels lit~n", [LitPixels, ?LED_COUNT]),
    ok.

% Process pixels recursively
process_pixels(<<>>, PixelIndex, LitCount) ->
    LitCount;
process_pixels(<<R:8, G:8, B:8, Rest/binary>>, PixelIndex, LitCount) ->
    % Map logical position to physical LED index based on layout
    MappedIndex = map_pixel_index(PixelIndex),
    
    % Update LED
    neopixel:set_pixel(MappedIndex, {R, G, B}),
    
    % Count lit pixels for logging
    NewLitCount = case R > 0 orelse G > 0 orelse B > 0 of
        true -> LitCount + 1;
        false -> LitCount
    end,
    
    process_pixels(Rest, PixelIndex + 1, NewLitCount).

% Map logical grid position to physical LED index
map_pixel_index(Index) ->
    X = Index rem ?GRID_WIDTH,
    Y = Index div ?GRID_WIDTH,
    
    % Apply serpentine pattern if enabled
    FinalX = case ?SERPENTINE_LAYOUT andalso (Y rem 2) =:= 1 of
        true -> ?GRID_WIDTH - 1 - X;  % Reverse direction on odd rows
        false -> X
    end,
    
    Y * ?GRID_WIDTH + FinalX. 