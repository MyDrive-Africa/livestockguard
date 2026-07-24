/**
 * @file hal_types.h
 * @brief Common HAL types for LivestockGuard firmware
 */
#ifndef HAL_TYPES_H
#define HAL_TYPES_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum {
    HAL_OK = 0, HAL_ERROR, HAL_BUSY, HAL_TIMEOUT,
    HAL_INVALID_PARAM, HAL_NOT_SUPPORTED, HAL_NOT_READY,
} hal_status_t;

typedef uint32_t hal_gpio_pin_t;
typedef enum { HAL_GPIO_STATE_LOW = 0, HAL_GPIO_STATE_HIGH = 1 } hal_gpio_state_t;
typedef enum { HAL_GPIO_EDGE_RISING, HAL_GPIO_EDGE_FALLING, HAL_GPIO_EDGE_BOTH } hal_gpio_edge_t;
typedef void (*hal_gpio_cb_t)(hal_gpio_pin_t pin, hal_gpio_state_t state);

typedef enum {
    HAL_POWER_MODE_RUN, HAL_POWER_MODE_SLEEP,
    HAL_POWER_MODE_DEEP_SLEEP, HAL_POWER_MODE_SHUTDOWN,
} hal_power_mode_t;

typedef struct {
    int32_t latitude;   /* Degrees * 1e7 */
    int32_t longitude;  /* Degrees * 1e7 */
} geo_point_t;

typedef struct {
    double latitude;
    double longitude;
    float altitude_m;
    float hdop;
    float speed_kmh;
    float heading_deg;
    uint8_t satellites;
    uint32_t timestamp;
    uint8_t fix_quality;
} gnss_fix_t;

typedef struct { int16_t x, y, z; } accel_data_t;

typedef enum {
    RADIO_PROTO_CELLULAR, RADIO_PROTO_LORAWAN,
    RADIO_PROTO_BLE, RADIO_PROTO_SATELLITE,
} radio_protocol_t;

typedef enum {
    RADIO_STATE_OFF, RADIO_STATE_IDLE, RADIO_STATE_TX,
    RADIO_STATE_RX, RADIO_STATE_SLEEP, RADIO_STATE_ERROR,
} radio_state_t;

#endif /* HAL_TYPES_H */
