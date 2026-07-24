/**
 * @file hal_radio.h
 * @brief Radio HAL interface
 */
#ifndef HAL_RADIO_H
#define HAL_RADIO_H
#include "hal_types.h"

typedef struct {
    int8_t tx_power_dbm;
    uint8_t retries;
    uint32_t timeout_ms;
    bool confirmed;
} radio_tx_params_t;

typedef void (*radio_rx_cb_t)(const uint8_t *data, size_t len, int8_t rssi);

hal_status_t hal_radio_init(radio_protocol_t protocol);
hal_status_t hal_radio_send(const uint8_t *data, size_t len, const radio_tx_params_t *params);
hal_status_t hal_radio_set_rx_callback(radio_rx_cb_t callback);
hal_status_t hal_radio_sleep(void);
hal_status_t hal_radio_wake(void);
int8_t hal_radio_get_rssi(void);
radio_state_t hal_radio_get_state(void);
bool hal_radio_is_available(void);

#endif
