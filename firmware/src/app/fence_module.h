/**
 * @file fence_module.h
 * @brief On-device geofence evaluation module
 */
#ifndef FENCE_MODULE_H
#define FENCE_MODULE_H
#include "hal_types.h"

typedef enum { FENCE_INSIDE, FENCE_WARNING, FENCE_BREACH, FENCE_ALERTED } fence_result_t;
typedef enum { FENCE_STATE_INSIDE, FENCE_STATE_WARNING, FENCE_STATE_BREACH, FENCE_STATE_ALERTED } fence_state_t;
typedef enum { FENCE_KEEP_INSIDE, FENCE_KEEP_OUTSIDE } fence_direction_t;

typedef struct {
    uint8_t id;
    uint8_t vertex_count;
    fence_direction_t direction;
    uint16_t grace_period_sec;
    bool deterrent_enabled;
    bool is_active;
    geo_point_t vertices[32];
} geofence_def_t;

void fence_module_init(void);
fence_result_t fence_module_evaluate(const gnss_fix_t *fix);
fence_state_t fence_module_get_state(uint8_t fence_id);
hal_status_t fence_module_set_geofence(const geofence_def_t *fence);
hal_status_t fence_module_delete_geofence(uint8_t fence_id);
uint8_t fence_module_get_active_count(void);

#endif
