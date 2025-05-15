#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/rmt.h"
#include "driver/gpio.h"
#include "esp_log.h"

#include "context.h"
#include "atom.h"
#include "term.h"
#include "bif.h"

static const char *TAG = "neopixel";

// WS2812B timing parameters
#define RMT_TICK_NS          (25)        // RMT tick period in nanoseconds
#define WS2812_T0H_NS        (350)       // 0 bit high time in nanoseconds
#define WS2812_T0L_NS        (900)       // 0 bit low time in nanoseconds
#define WS2812_T1H_NS        (900)       // 1 bit high time in nanoseconds
#define WS2812_T1L_NS        (350)       // 1 bit low time in nanoseconds
#define WS2812_RESET_US      (280)       // Reset time in microseconds

// Convert nanoseconds to RMT ticks
#define NS_TO_TICKS(ns)      ((ns) / RMT_TICK_NS)

// RMT channel
#define RMT_CHANNEL          RMT_CHANNEL_0

// NeoPixel driver state
typedef struct {
    int pin;                  // GPIO pin
    int num_leds;             // Number of LEDs in strip
    uint8_t *pixels;          // Pixel buffer (RGB format)
    rmt_item32_t *items;      // RMT items buffer
} neopixel_state_t;

// Global state
static neopixel_state_t *g_state = NULL;

// Convert RGB buffer to RMT items
static void neopixel_buf_to_rmt_items(const uint8_t *buf, int len, rmt_item32_t *items)
{
    // Convert each byte (8 bits) to RMT items
    for (int i = 0; i < len; i++) {
        uint8_t byte = buf[i];
        for (int j = 0; j < 8; j++) {
            int idx = i * 8 + j;
            if (byte & (1 << (7 - j))) {
                // 1 bit
                items[idx].level0 = 1;
                items[idx].duration0 = NS_TO_TICKS(WS2812_T1H_NS);
                items[idx].level1 = 0;
                items[idx].duration1 = NS_TO_TICKS(WS2812_T1L_NS);
            } else {
                // 0 bit
                items[idx].level0 = 1;
                items[idx].duration0 = NS_TO_TICKS(WS2812_T0H_NS);
                items[idx].level1 = 0;
                items[idx].duration1 = NS_TO_TICKS(WS2812_T0L_NS);
            }
        }
    }
}

// Initialize NeoPixel driver
static term nif_rmt_neopixel_init(Context *ctx, int argc, term argv[])
{
    if (argc != 2) {
        return BADARITY;
    }
    
    term pin_term = argv[0];
    term num_leds_term = argv[1];
    
    if (!term_is_integer(pin_term) || !term_is_integer(num_leds_term)) {
        return BADARG;
    }
    
    int pin = term_to_int(pin_term);
    int num_leds = term_to_int(num_leds_term);
    
    ESP_LOGI(TAG, "Initializing NeoPixel driver with %d LEDs on pin %d", num_leds, pin);
    
    // Allocate memory for state
    if (g_state != NULL) {
        // Free previous state
        if (g_state->pixels != NULL) {
            free(g_state->pixels);
        }
        if (g_state->items != NULL) {
            free(g_state->items);
        }
        free(g_state);
    }
    
    g_state = malloc(sizeof(neopixel_state_t));
    if (g_state == NULL) {
        return MEMORY_ERROR_ATOM;
    }
    
    g_state->pin = pin;
    g_state->num_leds = num_leds;
    
    // Allocate pixel buffer (3 bytes per LED: RGB)
    g_state->pixels = calloc(num_leds * 3, sizeof(uint8_t));
    if (g_state->pixels == NULL) {
        free(g_state);
        g_state = NULL;
        return MEMORY_ERROR_ATOM;
    }
    
    // Allocate RMT items buffer (8 bits per byte, 3 bytes per LED: RGB)
    g_state->items = calloc(num_leds * 3 * 8, sizeof(rmt_item32_t));
    if (g_state->items == NULL) {
        free(g_state->pixels);
        free(g_state);
        g_state = NULL;
        return MEMORY_ERROR_ATOM;
    }
    
    // Configure RMT
    rmt_config_t rmt_cfg = {
        .rmt_mode = RMT_MODE_TX,
        .channel = RMT_CHANNEL,
        .clk_div = 1,  // 80MHz / 1 = 80MHz -> 12.5ns per tick
        .gpio_num = pin,
        .mem_block_num = 1,
        .tx_config = {
            .loop_en = false,
            .carrier_en = false,
            .idle_output_en = true,
            .idle_level = 0
        }
    };
    
    ESP_ERROR_CHECK(rmt_config(&rmt_cfg));
    ESP_ERROR_CHECK(rmt_driver_install(RMT_CHANNEL, 0, 0));
    
    return OK_ATOM;
}

// Send pixel data to NeoPixel strip
static term nif_rmt_neopixel_show(Context *ctx, int argc, term argv[])
{
    if (argc != 1) {
        return BADARITY;
    }
    
    term binary_term = argv[0];
    if (!term_is_binary(binary_term)) {
        return BADARG;
    }
    
    if (g_state == NULL) {
        return ERROR_ATOM;
    }
    
    const char *buffer = term_binary_data(binary_term);
    int byte_count = term_binary_size(binary_term);
    
    // Validate binary size
    if (byte_count > g_state->num_leds * 3) {
        byte_count = g_state->num_leds * 3;
    }
    
    // Copy binary data to pixel buffer
    memcpy(g_state->pixels, buffer, byte_count);
    
    // Convert to RMT items
    neopixel_buf_to_rmt_items(g_state->pixels, byte_count, g_state->items);
    
    // Write items to RMT
    ESP_ERROR_CHECK(rmt_write_items(RMT_CHANNEL, g_state->items, byte_count * 8, false));
    
    // Wait for transmission to complete
    ESP_ERROR_CHECK(rmt_wait_tx_done(RMT_CHANNEL, pdMS_TO_TICKS(100)));
    
    return OK_ATOM;
}

// Register NIFs
static const struct Nif rmt_neopixel_init_nif = {
    .base.type = NIFFunctionType,
    .nif_ptr = nif_rmt_neopixel_init,
    .name = "rmt_neopixel_init",
    .arity = 2,
    .arg_type = ArgDefault
};

static const struct Nif rmt_neopixel_show_nif = {
    .base.type = NIFFunctionType,
    .nif_ptr = nif_rmt_neopixel_show,
    .name = "rmt_neopixel_show",
    .arity = 1,
    .arg_type = ArgDefault
};

// NIF table
const struct Nif *esp_neopixel_nif_get_nif(const char *nifname)
{
    if (strcmp("rmt_neopixel_init", nifname) == 0) {
        return &rmt_neopixel_init_nif;
    } else if (strcmp("rmt_neopixel_show", nifname) == 0) {
        return &rmt_neopixel_show_nif;
    } else {
        return NULL;
    }
} 