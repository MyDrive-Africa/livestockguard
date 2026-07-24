#ifndef EVENT_BUS_H
#define EVENT_BUS_H
#include "hal_types.h"

typedef enum {
    EVENT_POSITION_ACQUIRED, EVENT_GEOFENCE_BREACH,
    EVENT_THEFT_DETECTED, EVENT_TAMPER_DETECTED,
    EVENT_LOW_BATTERY, EVENT_COMMS_CONNECTED,
    EVENT_CONFIG_UPDATED, EVENT_OTA_AVAILABLE,
    EVENT_PANIC_START, EVENT_PANIC_CANCEL, EVENT_MAX,
} event_type_t;

typedef void (*event_handler_t)(event_type_t event, void *data);
void event_bus_init(void);
void event_bus_subscribe(event_type_t event, event_handler_t handler);
void event_bus_publish(event_type_t event, void *data);
#endif
