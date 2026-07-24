/**
 * @file event_bus.c
 * @brief Simple publish/subscribe event bus implementation
 */

#include "platform/event_bus.h"

#include <string.h>

#define MAX_HANDLERS 8

static event_handler_t g_handlers[EVENT_MAX][MAX_HANDLERS];
static uint8_t g_handler_count[EVENT_MAX];

void event_bus_init(void)
{
    memset(g_handlers, 0, sizeof(g_handlers));
    memset(g_handler_count, 0, sizeof(g_handler_count));
}

void event_bus_subscribe(event_type_t event, event_handler_t handler)
{
    if (event >= EVENT_MAX || !handler) {
        return;
    }
    if (g_handler_count[event] >= MAX_HANDLERS) {
        return;
    }
    g_handlers[event][g_handler_count[event]] = handler;
    g_handler_count[event]++;
}

void event_bus_publish(event_type_t event, void *data)
{
    if (event >= EVENT_MAX) {
        return;
    }
    for (uint8_t i = 0; i < g_handler_count[event]; i++) {
        if (g_handlers[event][i]) {
            g_handlers[event][i](event, data);
        }
    }
}
