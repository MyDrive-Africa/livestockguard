/**
 * @file hal_gnss.h
 * @brief GNSS Hardware Abstraction Layer
 */
#ifndef HAL_GNSS_H
#define HAL_GNSS_H
#include "hal_types.h"

#define GNSS_CONST_GPS     (1 << 0)
#define GNSS_CONST_GLONASS (1 << 1)
#define GNSS_CONST_BEIDOU  (1 << 2)
#define GNSS_CONST_ALL     (0x0F)

typedef struct {
    uint8_t constellation_mask;
    uint8_t min_satellites;
    float max_hdop;
    uint32_t fix_timeout_ms;
    bool low_power_mode;
} gnss_config_t;

hal_status_t hal_gnss_power_on(void);
hal_status_t hal_gnss_power_off(void);
hal_status_t hal_gnss_enter_backup(void);
hal_status_t hal_gnss_configure(const gnss_config_t *config);
hal_status_t hal_gnss_get_fix(gnss_fix_t *fix, uint32_t timeout_ms);
bool hal_gnss_has_fix(void);

#endif
