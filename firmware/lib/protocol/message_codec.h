/**
 * @file message_codec.h
 * @brief Message encoding/decoding for LivestockGuard protocol
 */
#ifndef MESSAGE_CODEC_H
#define MESSAGE_CODEC_H

#include "hal_types.h"
#include "services/config_service.h"

/** Message types */
typedef enum {
    MSG_TYPE_POSITION_BATCH  = 0x01,
    MSG_TYPE_GEOFENCE_ALERT  = 0x02,
    MSG_TYPE_THEFT_ALERT     = 0x03,
    MSG_TYPE_HEARTBEAT       = 0x04,
    MSG_TYPE_CONFIG_ACK      = 0x05,
    MSG_TYPE_OTA_REQUEST     = 0x06,
    MSG_TYPE_DOWNLINK_CONFIG = 0x80,
    MSG_TYPE_DOWNLINK_FENCE  = 0x81,
    MSG_TYPE_DOWNLINK_OTA    = 0x82,
    MSG_TYPE_DOWNLINK_CMD    = 0x83,
} msg_type_t;

/** Message priority levels */
typedef enum {
    MSG_PRIORITY_LOW      = 0,
    MSG_PRIORITY_NORMAL   = 1,
    MSG_PRIORITY_HIGH     = 2,
    MSG_PRIORITY_CRITICAL = 3,
} msg_priority_t;

/** Uplink message header */
typedef struct __attribute__((packed)) {
    uint8_t  version;
    uint8_t  msg_type;
    uint8_t  priority;
    uint16_t device_id;
    uint32_t timestamp;
    uint8_t  seq_num;
    uint8_t  payload_len;
} uplink_header_t;

/**
 * @brief Encode a batch of position records
 * @param records   Array of position records
 * @param count     Number of records
 * @param buf       Output buffer
 * @param buf_len   Output buffer size
 * @return Number of bytes written, or 0 on error
 */
size_t codec_encode_position_batch(const position_record_t *records, uint8_t count,
                                   uint8_t *buf, size_t buf_len);

/**
 * @brief Encode a geofence alert message
 * @param fence_id    Breached fence ID
 * @param state       Current fence state
 * @param fix         Position at breach
 * @param buf         Output buffer
 * @param buf_len     Output buffer size
 * @return Number of bytes written, or 0 on error
 */
size_t codec_encode_geofence_alert(uint8_t fence_id, uint8_t state,
                                   const gnss_fix_t *fix,
                                   uint8_t *buf, size_t buf_len);

/**
 * @brief Encode a theft alert message
 * @param trigger     Theft trigger type
 * @param fix         Position at detection
 * @param buf         Output buffer
 * @param buf_len     Output buffer size
 * @return Number of bytes written, or 0 on error
 */
size_t codec_encode_theft_alert(uint8_t trigger, const gnss_fix_t *fix,
                                uint8_t *buf, size_t buf_len);

/**
 * @brief Encode a heartbeat message
 * @param battery_pct   Battery percentage
 * @param fix           Last known position (may be NULL)
 * @param buf           Output buffer
 * @param buf_len       Output buffer size
 * @return Number of bytes written, or 0 on error
 */
size_t codec_encode_heartbeat(uint8_t battery_pct, const gnss_fix_t *fix,
                              uint8_t *buf, size_t buf_len);

/**
 * @brief Decode a downlink message with CRC verification
 * @param data      Received data buffer
 * @param len       Data length
 * @param msg_type  Output: decoded message type
 * @param payload   Output: pointer to payload start
 * @param pay_len   Output: payload length
 * @return HAL_OK on success, HAL_ERROR on CRC mismatch
 */
hal_status_t codec_decode_downlink(const uint8_t *data, size_t len,
                                   msg_type_t *msg_type,
                                   const uint8_t **payload, uint8_t *pay_len);

#endif /* MESSAGE_CODEC_H */
