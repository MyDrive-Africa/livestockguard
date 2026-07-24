/**
 * @file hal_accel.h
 * @brief Accelerometer HAL
 */
#ifndef HAL_ACCEL_H
#define HAL_ACCEL_H
#include "hal_types.h"

typedef enum { HAL_ACCEL_RATE_1HZ, HAL_ACCEL_RATE_25HZ, HAL_ACCEL_RATE_50HZ } hal_accel_rate_t;
typedef enum { HAL_ACCEL_RANGE_2G, HAL_ACCEL_RANGE_4G, HAL_ACCEL_RANGE_8G } hal_accel_range_t;

typedef struct {
    hal_accel_rate_t sample_rate;
    hal_accel_range_t range;
    bool fifo_enabled;
    uint8_t fifo_watermark;
    bool wakeup_enabled;
    uint16_t wakeup_threshold_mg;
} hal_accel_config_t;

typedef void (*hal_accel_cb_t)(void);

hal_status_t hal_accel_init(const hal_accel_config_t *config);
hal_status_t hal_accel_read(accel_data_t *data);
hal_status_t hal_accel_read_fifo(accel_data_t *buf, uint8_t max, uint8_t *actual);
hal_status_t hal_accel_set_motion_callback(hal_accel_cb_t cb);
hal_status_t hal_accel_low_power(void);

#endif
