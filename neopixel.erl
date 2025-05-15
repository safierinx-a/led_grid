%
% NeoPixel driver for AtomVM
% Uses ESP-IDF RMT (Remote Control) peripheral to drive WS2812B LEDs
%
-module(neopixel).
-export([init/2, set_pixel/2, set_pixel/3, show/0, clear/0]).

% Cached state
-define(STATE_ATOM, neopixel_state).

% Initialize NeoPixel driver
init(Pin, NumLeds) ->
    % Use esp:rmt_neopixel_init native function
    % This will initialize the RMT peripheral and buffer for the pixels
    case esp:rmt_neopixel_init(Pin, NumLeds) of
        ok ->
            % Create an ETS table to store pixel data
            ets:new(?STATE_ATOM, [set, public, named_table]),
            ets:insert(?STATE_ATOM, {num_leds, NumLeds}),
            ets:insert(?STATE_ATOM, {pin, Pin}),
            
            % Initialize buffer with all pixels off
            Buffer = create_buffer(NumLeds),
            ets:insert(?STATE_ATOM, {buffer, Buffer}),
            ok;
        Error ->
            Error
    end.

% Set a pixel with RGB tuple
set_pixel(Index, {R, G, B}) ->
    set_pixel(Index, R, G, B).

% Set a pixel with individual RGB components
set_pixel(Index, R, G, B) ->
    % Validate index
    [{num_leds, NumLeds}] = ets:lookup(?STATE_ATOM, num_leds),
    if
        Index >= 0 andalso Index < NumLeds ->
            % Update buffer
            [{buffer, Buffer}] = ets:lookup(?STATE_ATOM, buffer),
            NewBuffer = <<(binary:part(Buffer, 0, Index*3))/binary, R:8, G:8, B:8, 
                         (binary:part(Buffer, (Index+1)*3, NumLeds*3 - (Index+1)*3))/binary>>,
            ets:insert(?STATE_ATOM, {buffer, NewBuffer}),
            ok;
        true ->
            {error, invalid_index}
    end.

% Show the current buffer on the LEDs
show() ->
    [{buffer, Buffer}] = ets:lookup(?STATE_ATOM, buffer),
    % Use ESP-IDF to show the pixels
    % This function will convert RGB data to the specific bit timing 
    % needed by WS2812B LEDs and send it via RMT
    esp:rmt_neopixel_show(Buffer).

% Clear all pixels (set to off)
clear() ->
    [{num_leds, NumLeds}] = ets:lookup(?STATE_ATOM, num_leds),
    Buffer = create_buffer(NumLeds),
    ets:insert(?STATE_ATOM, {buffer, Buffer}),
    ok.

% Create an empty buffer with all pixels off
create_buffer(NumLeds) ->
    list_to_binary(lists:duplicate(NumLeds * 3, 0)). 