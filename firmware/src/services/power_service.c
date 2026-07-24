/**
 * @file power_service.c
 * @brief Power management service implementation
 */

#include "services/power_service.h"
#include "services/config_service.h"
#include "hal_power.h"
#include "platform/log_system.h"

static power_profile_t g_current_profile;

void power_service_init(void)
{
    const device_config_t *cfg = config_service_get();
    g_current_profile = cfg->power_profile;

    uint8_t batt = hal_power_get_battery_pct();
    LOG_INFO("Power service init: battery=%d%%, profile=%d", batt, g_current_profile);
}

void power_service_enter_sleep(void)
{
    uint32_t sleep_sec;

    switch (g_current_profile) {
    case POWER_PROFILE_MAX_LIFE:  sleep_sec = 3600;  break;
    case POWER_PROFILE_BALANCED:  sleep_sec = 900;   break;
    case POWER_PROFILE_HIGH_TRACK: sleep_sec = 300;  break;
    case POWER_PROFILE_PANIC:     sleep_sec = 30;    break;
    case POWER_PROFILE_RECOVERY:  sleep_sec = 1800;  break;
    default:                      sleep_sec = 900;   break;
    }

    LOG_DEBUG("Sleeping %lu seconds (profile=%d)", (unsigned long)sleep_sec, g_current_profile);
    hal_power_sleep_seconds(sleep_sec);
}

void power_service_delay_ms(uint32_t ms)
{
    /* Simple blocking delay: sleep in 1-second increments */
    uint32_t seconds = ms / 1000;
    if (seconds > 0) {
        hal_power_sleep_seconds(seconds);
    }
}

void power_service_set_profile(power_profile_t profile)
{
    g_current_profile = profile;
    LOG_INFO("Power profile set to %d", profile);
}

uint8_t power_service_get_battery_pct(void)
{
    return hal_power_get_battery_pct();
}
