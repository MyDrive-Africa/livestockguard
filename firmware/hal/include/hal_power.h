/**
 * @file hal_power.h
 * @brief Power Management HAL
 */
#ifndef HAL_POWER_H
#define HAL_POWER_H
#include "hal_types.h"

typedef enum {
    HAL_WAKE_RTC = (1<<0), HAL_WAKE_ACCEL = (1<<1),
    HAL_WAKE_RADIO = (1<<2), HAL_WAKE_GPIO = (1<<3),
} hal_wake_source_t;

hal_status_t hal_power_enter_mode(hal_power_mode_t mode, uint32_t wake_sources);
hal_status_t hal_power_sleep_seconds(uint32_t seconds);
hal_wake_source_t hal_power_get_wake_source(void);
uint16_t hal_power_get_battery_mv(void);
uint8_t hal_power_get_battery_pct(void);
bool hal_power_is_charging(void);
void hal_power_wdt_feed(void);
hal_status_t hal_power_wdt_init(uint32_t timeout_ms);
void hal_power_reset(void) __attribute__((noreturn));

#endif
