/**
 * @file health_module.c
 * @brief Animal health and activity monitoring implementation
 */

#include "app/health_module.h"
#include "services/sensor_service.h"
#include "services/config_service.h"
#include "platform/log_system.h"

static activity_state_t g_activity;
static uint32_t g_activity_start;
static uint32_t g_no_movement_time;
static uint32_t g_last_movement_ts;

void health_module_init(void)
{
    g_activity = ACTIVITY_UNKNOWN;
    g_activity_start = 0;
    g_no_movement_time = 0;
    g_last_movement_ts = 0;
}

void health_module_update(const gnss_fix_t *fix)
{
    /* Read accelerometer data */
    accel_data_t sample;
    sensor_service_read_accel(&sample);
    float magnitude = sensor_service_get_magnitude();
    bool motion = sensor_service_motion_detected();
    (void)magnitude; /* magnitude used indirectly via variance */

    /* Classify activity based on variance thresholds */
    /* Variance is computed internally by sensor_service */
    activity_state_t new_activity;

    if (!motion) {
        /* variance < 0.01 */
        new_activity = ACTIVITY_RESTING;
    } else {
        /* Use magnitude-based heuristic correlated with variance */
        float mag = sensor_service_get_magnitude();
        float diff = (mag > 1.0f) ? (mag - 1.0f) : (1.0f - mag);
        if (diff < 0.05f) {
            new_activity = ACTIVITY_GRAZING;
        } else if (diff < 0.15f) {
            new_activity = ACTIVITY_WALKING;
        } else {
            new_activity = ACTIVITY_RUNNING;
        }
    }

    /* Override: high speed from GNSS means transport */
    if (fix->speed_kmh > 40.0f) {
        new_activity = ACTIVITY_TRANSPORT;
    }

    if (new_activity != g_activity) {
        g_activity = new_activity;
        g_activity_start = fix->timestamp;
    }

    /* Track no-movement duration for mortality detection */
    if (motion) {
        g_last_movement_ts = fix->timestamp;
        g_no_movement_time = 0;
    } else {
        if (g_last_movement_ts > 0) {
            g_no_movement_time = (fix->timestamp - g_last_movement_ts) / 60;
        }
    }
}

activity_state_t health_module_get_activity(void)
{
    return g_activity;
}

health_event_t health_module_check_events(void)
{
    const device_config_t *cfg = config_service_get();

    if (g_no_movement_time >= cfg->mortality_timeout_min) {
        LOG_WARN("Mortality risk: no movement for %lu min", (unsigned long)g_no_movement_time);
        return HEALTH_EVENT_MORTALITY_RISK;
    }
    return HEALTH_EVENT_NONE;
}
