/**
 * @file fence_module.c
 * @brief On-device geofence evaluation with state machine
 */

#include "app/fence_module.h"
#include "platform/nv_store.h"
#include "platform/log_system.h"
#include "geofence/point_in_polygon.h"

#include <string.h>

#ifndef MAX_GEOFENCES
#define MAX_GEOFENCES 8
#endif

/** Per-fence runtime state */
typedef struct {
    fence_state_t state;
    uint32_t exit_time;         /**< Timestamp when animal exited fence */
    uint8_t consecutive_out;    /**< Consecutive evaluations outside fence */
} fence_runtime_t;

static geofence_def_t g_fences[MAX_GEOFENCES];
static fence_runtime_t g_runtime[MAX_GEOFENCES];
static uint8_t g_fence_count;

void fence_module_init(void)
{
    memset(g_fences, 0, sizeof(g_fences));
    memset(g_runtime, 0, sizeof(g_runtime));
    g_fence_count = 0;

    /* Load stored geofences from non-volatile storage */
    if (nv_store_read(NV_KEY_GEOFENCES, g_fences, sizeof(g_fences)) == HAL_OK) {
        for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
            if (g_fences[i].is_active) {
                g_fence_count++;
                g_runtime[i].state = FENCE_STATE_INSIDE;
            }
        }
        LOG_INFO("Loaded %d geofences from NV", g_fence_count);
    }
}

/**
 * @brief Evaluate a single fence against current position
 * @return The result for this fence after state transitions
 */
static fence_result_t evaluate_single_fence(uint8_t idx, const gnss_fix_t *fix)
{
    geofence_def_t *fence = &g_fences[idx];
    fence_runtime_t *rt = &g_runtime[idx];

    if (!fence->is_active) {
        return FENCE_INSIDE;
    }

    /* Convert fix to geo_point_t (lat/lon * 1e7) */
    geo_point_t point;
    point.latitude = (int32_t)(fix->latitude * 1e7);
    point.longitude = (int32_t)(fix->longitude * 1e7);

    /* Ray-casting point-in-polygon test */
    bool inside = point_in_polygon(&point, fence->vertices, fence->vertex_count);

    /* For KEEP_OUTSIDE fences, invert the logic */
    if (fence->direction == FENCE_KEEP_OUTSIDE) {
        inside = !inside;
    }

    /* State machine transitions */
    switch (rt->state) {
    case FENCE_STATE_INSIDE:
        if (!inside) {
            rt->state = FENCE_STATE_WARNING;
            rt->exit_time = fix->timestamp;
            rt->consecutive_out = 1;
            LOG_WARN("Fence %d: INSIDE -> WARNING", fence->id);
        }
        break;

    case FENCE_STATE_WARNING:
        if (inside) {
            /* Returned within grace period */
            rt->state = FENCE_STATE_INSIDE;
            rt->consecutive_out = 0;
            LOG_INFO("Fence %d: WARNING -> INSIDE (returned)", fence->id);
        } else {
            rt->consecutive_out++;
            uint32_t elapsed = fix->timestamp - rt->exit_time;
            if (elapsed >= fence->grace_period_sec) {
                rt->state = FENCE_STATE_BREACH;
                LOG_WARN("Fence %d: WARNING -> BREACH (grace expired)", fence->id);
            }
        }
        break;

    case FENCE_STATE_BREACH:
        if (inside) {
            rt->state = FENCE_STATE_INSIDE;
            rt->consecutive_out = 0;
            LOG_INFO("Fence %d: BREACH -> INSIDE (returned)", fence->id);
        } else {
            rt->consecutive_out++;
            if (rt->consecutive_out >= 3) {
                rt->state = FENCE_STATE_ALERTED;
                LOG_WARN("Fence %d: BREACH -> ALERTED (3 consecutive)", fence->id);
            }
        }
        break;

    case FENCE_STATE_ALERTED:
        if (inside) {
            rt->state = FENCE_STATE_INSIDE;
            rt->consecutive_out = 0;
            LOG_INFO("Fence %d: ALERTED -> INSIDE (returned)", fence->id);
        }
        break;
    }

    return (fence_result_t)rt->state;
}

fence_result_t fence_module_evaluate(const gnss_fix_t *fix)
{
    fence_result_t worst = FENCE_INSIDE;

    for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
        if (!g_fences[i].is_active) {
            continue;
        }
        fence_result_t result = evaluate_single_fence(i, fix);
        if (result > worst) {
            worst = result;
        }
    }

    return worst;
}

fence_state_t fence_module_get_state(uint8_t fence_id)
{
    for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
        if (g_fences[i].is_active && g_fences[i].id == fence_id) {
            return g_runtime[i].state;
        }
    }
    return FENCE_STATE_INSIDE;
}

hal_status_t fence_module_set_geofence(const geofence_def_t *fence)
{
    /* Find empty slot or existing fence with same ID */
    for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
        if (!g_fences[i].is_active || g_fences[i].id == fence->id) {
            memcpy(&g_fences[i], fence, sizeof(geofence_def_t));
            g_runtime[i].state = FENCE_STATE_INSIDE;
            g_runtime[i].exit_time = 0;
            g_runtime[i].consecutive_out = 0;
            nv_store_write(NV_KEY_GEOFENCES, g_fences, sizeof(g_fences));
            g_fence_count = fence_module_get_active_count();
            return HAL_OK;
        }
    }
    return HAL_ERROR;
}

hal_status_t fence_module_delete_geofence(uint8_t fence_id)
{
    for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
        if (g_fences[i].is_active && g_fences[i].id == fence_id) {
            memset(&g_fences[i], 0, sizeof(geofence_def_t));
            memset(&g_runtime[i], 0, sizeof(fence_runtime_t));
            nv_store_write(NV_KEY_GEOFENCES, g_fences, sizeof(g_fences));
            g_fence_count--;
            return HAL_OK;
        }
    }
    return HAL_INVALID_PARAM;
}

uint8_t fence_module_get_active_count(void)
{
    uint8_t count = 0;
    for (uint8_t i = 0; i < MAX_GEOFENCES; i++) {
        if (g_fences[i].is_active) {
            count++;
        }
    }
    return count;
}
