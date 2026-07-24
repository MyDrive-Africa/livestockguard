#ifndef POWER_SERVICE_H
#define POWER_SERVICE_H
#include "hal_types.h"
#include "services/config_service.h"
void power_service_init(void);
void power_service_enter_sleep(void);
void power_service_delay_ms(uint32_t ms);
void power_service_set_profile(power_profile_t profile);
uint8_t power_service_get_battery_pct(void);
#endif
