/**
 * @file config_service.c
 * @brief Configuration management service implementation
 */

#include "services/config_service.h"
#include "platform/nv_store.h"
#include "platform/log_system.h"

#include <string.h>

static device_config_t g_config = {
    .fix_interval_normal_sec    = 900,
    .fix_interval_alert_sec     = 30,
    .max_fix_attempts           = 3,
    .fix_timeout_ms             = 90000,
    .geofence_grace_period_sec  = 60,
    .geofence_deterrent_enabled = false,
    .batch_interval_sec         = 14400,
    .batch_max_records          = 16,
    .power_profile              = POWER_PROFILE_BALANCED,
    .low_battery_threshold      = 10,
    .tamper_detection_enabled   = true,
    .night_movement_enabled     = true,
    .quiet_hours_start          = 22,
    .quiet_hours_end            = 5,
    .transport_speed_threshold  = 40,
    .activity_monitor_enabled   = true,
    .mortality_timeout_min      = 360,
};

void config_service_init(void)
{
    device_config_t stored;
    if (nv_store_read(NV_KEY_CONFIG, &stored, sizeof(stored)) == HAL_OK) {
        memcpy(&g_config, &stored, sizeof(device_config_t));
        LOG_INFO("Config loaded from NV storage");
    } else {
        LOG_INFO("Using default configuration");
    }
}

const device_config_t *config_service_get(void)
{
    return &g_config;
}

hal_status_t config_service_update(const device_config_t *new_config)
{
    if (!new_config) {
        return HAL_INVALID_PARAM;
    }

    /* Basic validation */
    if (new_config->fix_timeout_ms < 1000 || new_config->fix_timeout_ms > 300000) {
        return HAL_INVALID_PARAM;
    }
    if (new_config->low_battery_threshold > 100) {
        return HAL_INVALID_PARAM;
    }
    if (new_config->quiet_hours_start > 23 || new_config->quiet_hours_end > 23) {
        return HAL_INVALID_PARAM;
    }

    memcpy(&g_config, new_config, sizeof(device_config_t));

    hal_status_t status = nv_store_write(NV_KEY_CONFIG, &g_config, sizeof(g_config));
    if (status != HAL_OK) {
        LOG_ERROR("Failed to persist config");
        return status;
    }
    LOG_INFO("Configuration updated and persisted");
    return HAL_OK;
}
