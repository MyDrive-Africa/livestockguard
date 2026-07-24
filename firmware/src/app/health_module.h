/**
 * @file health_module.h
 * @brief Animal health and activity monitoring
 */
#ifndef HEALTH_MODULE_H
#define HEALTH_MODULE_H
#include "hal_types.h"

typedef enum { ACTIVITY_RESTING, ACTIVITY_GRAZING, ACTIVITY_WALKING, ACTIVITY_RUNNING, ACTIVITY_TRANSPORT, ACTIVITY_UNKNOWN } activity_state_t;
typedef enum { HEALTH_EVENT_NONE, HEALTH_EVENT_ANOMALY, HEALTH_EVENT_MORTALITY_RISK, HEALTH_EVENT_CALVING, HEALTH_EVENT_FEVER } health_event_t;

void health_module_init(void);
void health_module_update(const gnss_fix_t *fix);
activity_state_t health_module_get_activity(void);
health_event_t health_module_check_events(void);

#endif
