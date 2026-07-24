/**
 * @file gnss_service.c
 * @brief GNSS acquisition service implementation
 */

#include "services/gnss_service.h"
#include "services/config_service.h"
#include "hal_gnss.h"
#include "platform/log_system.h"

#include <string.h>

static gnss_fix_t g_last_fix;
static bool g_has_fix = false;

void gnss_service_init(void)
{
    gnss_config_t cfg = {
        .constellation_mask = GNSS_CONST_ALL,
        .min_satellites     = 4,
        .max_hdop           = 5.0f,
        .fix_timeout_ms     = 90000,
        .low_power_mode     = true,
    };
    hal_gnss_configure(&cfg);
    memset(&g_last_fix, 0, sizeof(g_last_fix));
    g_has_fix = false;
    LOG_INFO("GNSS service initialized");
}

bool gnss_service_acquire_fix(void)
{
    const device_config_t *cfg = config_service_get();
    gnss_fix_t fix;

    hal_gnss_power_on();

    hal_status_t status = hal_gnss_get_fix(&fix, cfg->fix_timeout_ms);
    if (status != HAL_OK) {
        LOG_WARN("GNSS fix timeout");
        hal_gnss_enter_backup();
        return false;
    }

    /* Validate fix quality */
    if (fix.satellites < 4 || fix.hdop > 5.0f || fix.speed_kmh > 150.0f) {
        LOG_WARN("GNSS fix invalid: sats=%d hdop=%.1f spd=%.1f",
                 fix.satellites, fix.hdop, fix.speed_kmh);
        hal_gnss_enter_backup();
        return false;
    }

    memcpy(&g_last_fix, &fix, sizeof(gnss_fix_t));
    g_has_fix = true;
    hal_gnss_enter_backup();
    LOG_DEBUG("Fix acquired: sats=%d hdop=%.1f", fix.satellites, fix.hdop);
    return true;
}

void gnss_service_get_last_fix(gnss_fix_t *fix)
{
    if (fix) {
        memcpy(fix, &g_last_fix, sizeof(gnss_fix_t));
    }
}
