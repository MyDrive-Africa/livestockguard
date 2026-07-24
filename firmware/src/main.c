/**
 * @file main.c
 * @brief LivestockGuard firmware main state machine
 */

#include "hal_types.h"
#include "hal_power.h"
#include "hal_gnss.h"
#include "hal_radio.h"
#include "hal_accel.h"

#include "platform/event_bus.h"
#include "platform/log_system.h"
#include "platform/nv_store.h"

#include "services/gnss_service.h"
#include "services/comms_service.h"
#include "services/power_service.h"
#include "services/sensor_service.h"
#include "services/config_service.h"

#include "app/fence_module.h"
#include "app/health_module.h"
#include "app/theft_module.h"
#include "app/track_module.h"
#include "app/ota_module.h"

/** Firmware state machine states */
typedef enum {
    STATE_INIT,
    STATE_SLEEP,
    STATE_GPS_ACQUIRE,
    STATE_PROCESS,
    STATE_COMMUNICATE,
    STATE_PANIC,
    STATE_OTA,
    STATE_SAFE_MODE,
} firmware_state_t;

static firmware_state_t g_state = STATE_INIT;
static gnss_fix_t g_last_fix;

/**
 * @brief Initialize all system services and modules
 */
static void system_init(void)
{
    log_init();
    LOG_INFO("LivestockGuard firmware v%d.%d.%d starting", 1, 0, 0);

    nv_store_init();
    event_bus_init();
    config_service_init();
    power_service_init();
    sensor_service_init();
    gnss_service_init();
    comms_service_init();

    fence_module_init();
    health_module_init();
    theft_module_init();
    track_module_init();

#ifdef FEATURE_OTA
    ota_module_init();
#endif

    hal_power_wdt_init(30000);
    LOG_INFO("System init complete");
}

/**
 * @brief Determine if it is time to transmit buffered data
 */
static bool should_transmit(void)
{
    if (comms_service_has_critical()) {
        return true;
    }
    if (comms_service_batch_interval_elapsed()) {
        return true;
    }
    if (comms_service_buffer_nearly_full()) {
        return true;
    }
    return false;
}

/**
 * @brief Execute one iteration of the firmware state machine
 */
static void run_state_machine(void)
{
    const device_config_t *cfg = config_service_get();

    switch (g_state) {
    case STATE_INIT:
        system_init();
        g_state = STATE_SLEEP;
        break;

    case STATE_SLEEP:
        power_service_enter_sleep();
        g_state = STATE_GPS_ACQUIRE;
        break;

    case STATE_GPS_ACQUIRE:
        if (gnss_service_acquire_fix()) {
            gnss_service_get_last_fix(&g_last_fix);
            g_state = STATE_PROCESS;
        } else {
            LOG_WARN("GPS fix failed");
            g_state = STATE_SLEEP;
        }
        break;

    case STATE_PROCESS:
        /* Record position */
        track_module_record_position(&g_last_fix);

        /* Evaluate geofence */
        {
            fence_result_t fence = fence_module_evaluate(&g_last_fix);
            if (fence == FENCE_BREACH || fence == FENCE_ALERTED) {
                event_bus_publish(EVENT_GEOFENCE_BREACH, NULL);
            }
        }

        /* Health monitoring */
        health_module_update(&g_last_fix);
        if (health_module_check_events() != HEALTH_EVENT_NONE) {
            LOG_INFO("Health event detected");
        }

        /* Theft detection */
        {
            theft_result_t theft = theft_module_check(&g_last_fix);
            if (theft == THEFT_DETECTED) {
                event_bus_publish(EVENT_THEFT_DETECTED, NULL);
                event_bus_publish(EVENT_PANIC_START, NULL);
                power_service_set_profile(POWER_PROFILE_PANIC);
                g_state = STATE_PANIC;
                break;
            }
        }

        /* Decide next state */
        if (should_transmit()) {
            g_state = STATE_COMMUNICATE;
        } else {
            g_state = STATE_SLEEP;
        }
        break;

    case STATE_COMMUNICATE:
        comms_service_transmit_queue();
        comms_service_check_downlink();

#ifdef FEATURE_OTA
        if (ota_module_is_available()) {
            g_state = STATE_OTA;
            break;
        }
#endif
        g_state = STATE_SLEEP;
        break;

    case STATE_PANIC:
        /* High-frequency GPS fixes every 30 seconds */
        power_service_delay_ms(30000);
        if (gnss_service_acquire_fix()) {
            gnss_service_get_last_fix(&g_last_fix);
            track_module_record_position(&g_last_fix);
            comms_service_send_immediate();
        }
        /* Check if panic cancelled */
        if (comms_service_panic_cancelled() || !theft_module_is_panic_active()) {
            power_service_set_profile(cfg->power_profile);
            g_state = STATE_SLEEP;
        }
        break;

    case STATE_OTA:
#ifdef FEATURE_OTA
        {
            ota_state_t ota = ota_module_process();
            if (ota == OTA_STATE_IDLE || ota == OTA_STATE_ERROR) {
                g_state = STATE_SLEEP;
            }
            /* Stay in OTA state while downloading/verifying */
        }
#else
        g_state = STATE_SLEEP;
#endif
        break;

    case STATE_SAFE_MODE:
        /* Minimal operation: heartbeat only */
        LOG_ERROR("Safe mode active");
        power_service_delay_ms(60000);
        comms_service_transmit_queue();
        break;
    }
}

/**
 * @brief Firmware entry point
 */
int main(void)
{
    g_state = STATE_INIT;

    while (1) {
        hal_power_wdt_feed();
        run_state_machine();
    }

    /* Should never reach here */
    return 0;
}
