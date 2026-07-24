/**
 * @file config_service.h
 * @brief Device configuration management
 */
#ifndef CONFIG_SERVICE_H
#define CONFIG_SERVICE_H
#include "hal_types.h"

typedef enum { POWER_PROFILE_MAX_LIFE, POWER_PROFILE_BALANCED, POWER_PROFILE_HIGH_TRACK, POWER_PROFILE_PANIC, POWER_PROFILE_RECOVERY } power_profile_t;

typedef struct __attribute__((packed)) {
    uint32_t timestamp;
    int32_t lat_offset;
    int32_t lon_offset;
    uint8_t speed;
    uint8_t heading;
    uint8_t hdop_x10;
    uint8_t flags;
} position_record_t;

typedef struct {
    uint16_t fix_interval_normal_sec;
    uint16_t fix_interval_alert_sec;
    uint8_t max_fix_attempts;
    uint16_t fix_timeout_ms;
    uint16_t geofence_grace_period_sec;
    bool geofence_deterrent_enabled;
    uint16_t batch_interval_sec;
    uint8_t batch_max_records;
    power_profile_t power_profile;
    uint8_t low_battery_threshold;
    bool tamper_detection_enabled;
    bool night_movement_enabled;
    uint8_t quiet_hours_start;
    uint8_t quiet_hours_end;
    uint8_t transport_speed_threshold;
    bool activity_monitor_enabled;
    uint16_t mortality_timeout_min;
} device_config_t;

void config_service_init(void);
const device_config_t *config_service_get(void);
hal_status_t config_service_update(const device_config_t *new_config);

#endif
