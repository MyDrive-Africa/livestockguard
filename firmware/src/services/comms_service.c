/**
 * @file comms_service.c
 * @brief Communications management service
 */

#include "services/comms_service.h"
#include "services/config_service.h"
#include "hal_radio.h"
#include "collections/ring_buffer.h"
#include "protocol/message_codec.h"
#include "platform/event_bus.h"
#include "platform/log_system.h"

#include <string.h>

#define COMMS_QUEUE_SIZE    256
#define COMMS_MSG_SIZE      280

static uint8_t g_queue_storage[COMMS_QUEUE_SIZE * COMMS_MSG_SIZE];
static ring_buffer_t g_msg_queue;
static uint32_t g_last_batch_time;
static bool g_panic_cancelled;

/* Simulated system tick (provided externally or by HAL) */
extern uint32_t hal_get_tick_seconds(void);

void comms_service_init(void)
{
    ring_buffer_init(&g_msg_queue, g_queue_storage, COMMS_MSG_SIZE, COMMS_QUEUE_SIZE);
    hal_radio_init(RADIO_PROTO_LORAWAN);
    g_last_batch_time = 0;
    g_panic_cancelled = false;
    LOG_INFO("Comms service initialized");
}

void comms_service_transmit_queue(void)
{
    uint8_t msg[COMMS_MSG_SIZE];
    radio_tx_params_t params = {
        .tx_power_dbm = 14,
        .retries      = 3,
        .timeout_ms   = 10000,
        .confirmed    = true,
    };

    while (ring_buffer_pop(&g_msg_queue, msg)) {
        /* First byte is payload length */
        uint8_t len = msg[0];
        hal_radio_send(&msg[1], len, &params);
    }
    g_last_batch_time = hal_get_tick_seconds();
}

void comms_service_send_immediate(void)
{
    uint8_t msg[COMMS_MSG_SIZE];
    radio_tx_params_t params = {
        .tx_power_dbm = 20,
        .retries      = 5,
        .timeout_ms   = 15000,
        .confirmed    = true,
    };

    /* Send most recent critical message */
    if (ring_buffer_pop(&g_msg_queue, msg)) {
        uint8_t len = msg[0];
        hal_radio_send(&msg[1], len, &params);
    }
}

void comms_service_check_downlink(void)
{
    /* Radio RX callback handles incoming data asynchronously.
     * This function processes any pending decoded commands. */
    (void)0; /* Placeholder: RX handled via hal_radio_set_rx_callback */
}

bool comms_service_has_critical(void)
{
    /* Check if buffer contains critical-priority messages by peeking */
    uint8_t msg[COMMS_MSG_SIZE];
    if (ring_buffer_peek(&g_msg_queue, msg)) {
        /* Priority stored at byte offset after length (index 3 per uplink header) */
        if (msg[3] >= MSG_PRIORITY_CRITICAL) {
            return true;
        }
    }
    return false;
}

bool comms_service_batch_interval_elapsed(void)
{
    const device_config_t *cfg = config_service_get();
    uint32_t now = hal_get_tick_seconds();
    return (now - g_last_batch_time) >= cfg->batch_interval_sec;
}

bool comms_service_buffer_nearly_full(void)
{
    size_t count = ring_buffer_count(&g_msg_queue);
    return count > (COMMS_QUEUE_SIZE * 80 / 100);
}

bool comms_service_panic_cancelled(void)
{
    bool cancelled = g_panic_cancelled;
    g_panic_cancelled = false;
    return cancelled;
}
