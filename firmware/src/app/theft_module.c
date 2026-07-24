/**
 * @file theft_module.c
 * @brief Anti-theft detection module implementation
 */

#include "app/theft_module.h"
#include "services/config_service.h"
#include "platform/log_system.h"

static theft_trigger_t g_trigger;
static bool g_panic_active;
static uint32_t g_high_speed_start;

void theft_module_init(void)
{
    g_trigger = THEFT_TRIGGER_NONE;
    g_panic_active = false;
    g_high_speed_start = 0;
}

theft_result_t theft_module_check(const gnss_fix_t *fix)
{
    const device_config_t *cfg = config_service_get();

    /* Transport detection: speed above threshold for > 30 seconds */
    if (fix->speed_kmh > (float)cfg->transport_speed_threshold) {
        if (g_high_speed_start == 0) {
            g_high_speed_start = fix->timestamp;
        } else if ((fix->timestamp - g_high_speed_start) > 30) {
            g_trigger = THEFT_TRIGGER_TRANSPORT;
            g_panic_active = true;
            LOG_WARN("Theft detected: transport (speed=%.1f)", fix->speed_kmh);
            return THEFT_DETECTED;
        }
    } else {
        g_high_speed_start = 0;
    }

    /* Night movement detection */
    if (cfg->night_movement_enabled) {
        /* Extract hour from timestamp (UTC seconds -> hour) */
        uint8_t hour = (uint8_t)((fix->timestamp / 3600) % 24);
        bool in_quiet_hours;

        if (cfg->quiet_hours_start > cfg->quiet_hours_end) {
            /* Wraps midnight: e.g. 22:00 - 05:00 */
            in_quiet_hours = (hour >= cfg->quiet_hours_start || hour < cfg->quiet_hours_end);
        } else {
            in_quiet_hours = (hour >= cfg->quiet_hours_start && hour < cfg->quiet_hours_end);
        }

        if (in_quiet_hours && fix->speed_kmh > 2.0f) {
            g_trigger = THEFT_TRIGGER_NIGHT_MOVE;
            g_panic_active = true;
            LOG_WARN("Theft detected: night movement (hour=%d)", hour);
            return THEFT_DETECTED;
        }
    }

    return THEFT_NONE;
}

theft_trigger_t theft_module_get_trigger(void)
{
    return g_trigger;
}

void theft_module_cancel_panic(void)
{
    g_panic_active = false;
    g_trigger = THEFT_TRIGGER_NONE;
    LOG_INFO("Theft panic cancelled");
}

bool theft_module_is_panic_active(void)
{
    return g_panic_active;
}
