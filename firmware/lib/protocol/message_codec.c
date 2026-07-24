/**
 * @file message_codec.c
 * @brief Message encoding/decoding for LivestockGuard protocol
 */

#include "protocol/message_codec.h"
#include "protocol/crc16.h"
#include <string.h>

#define PROTOCOL_VERSION  0x01
#define HEADER_SIZE       sizeof(uplink_header_t)
#define CRC_SIZE          2

static uint8_t g_seq_num = 0;
static uint16_t g_device_id = 0;

/**
 * @brief Write a standard uplink header into the buffer
 */
static size_t write_header(uint8_t *buf, msg_type_t type, msg_priority_t priority,
                           uint32_t timestamp, uint8_t payload_len)
{
    uplink_header_t *hdr = (uplink_header_t *)buf;
    hdr->version = PROTOCOL_VERSION;
    hdr->msg_type = (uint8_t)type;
    hdr->priority = (uint8_t)priority;
    hdr->device_id = g_device_id;
    hdr->timestamp = timestamp;
    hdr->seq_num = g_seq_num++;
    hdr->payload_len = payload_len;
    return HEADER_SIZE;
}

/**
 * @brief Append CRC-16 to the end of a message
 */
static size_t append_crc(uint8_t *buf, size_t msg_len)
{
    uint16_t crc = crc16_compute(buf, msg_len);
    buf[msg_len] = (uint8_t)(crc >> 8);
    buf[msg_len + 1] = (uint8_t)(crc & 0xFF);
    return msg_len + CRC_SIZE;
}

size_t codec_encode_position_batch(const position_record_t *records, uint8_t count,
                                   uint8_t *buf, size_t buf_len)
{
    if (records == NULL || buf == NULL || count == 0) {
        return 0;
    }

    size_t payload_size = (size_t)count * sizeof(position_record_t);
    size_t total_size = HEADER_SIZE + payload_size + CRC_SIZE;

    if (buf_len < total_size) {
        return 0;
    }

    size_t offset = write_header(buf, MSG_TYPE_POSITION_BATCH, MSG_PRIORITY_NORMAL,
                                 records[0].timestamp, (uint8_t)payload_size);

    memcpy(buf + offset, records, payload_size);
    offset += payload_size;

    return append_crc(buf, offset);
}

size_t codec_encode_geofence_alert(uint8_t fence_id, uint8_t state,
                                   const gnss_fix_t *fix,
                                   uint8_t *buf, size_t buf_len)
{
    if (fix == NULL || buf == NULL) {
        return 0;
    }

    /* Payload: fence_id(1) + state(1) + lat(4) + lon(4) = 10 bytes */
    uint8_t payload_len = 10;
    size_t total_size = HEADER_SIZE + payload_len + CRC_SIZE;

    if (buf_len < total_size) {
        return 0;
    }

    size_t offset = write_header(buf, MSG_TYPE_GEOFENCE_ALERT, MSG_PRIORITY_CRITICAL,
                                 fix->timestamp, payload_len);

    buf[offset++] = fence_id;
    buf[offset++] = state;

    int32_t lat = (int32_t)(fix->latitude * 1e7);
    int32_t lon = (int32_t)(fix->longitude * 1e7);
    memcpy(buf + offset, &lat, 4); offset += 4;
    memcpy(buf + offset, &lon, 4); offset += 4;

    return append_crc(buf, offset);
}

size_t codec_encode_theft_alert(uint8_t trigger, const gnss_fix_t *fix,
                                uint8_t *buf, size_t buf_len)
{
    if (fix == NULL || buf == NULL) {
        return 0;
    }

    /* Payload: trigger(1) + lat(4) + lon(4) + speed(1) + heading(2) = 12 bytes */
    uint8_t payload_len = 12;
    size_t total_size = HEADER_SIZE + payload_len + CRC_SIZE;

    if (buf_len < total_size) {
        return 0;
    }

    size_t offset = write_header(buf, MSG_TYPE_THEFT_ALERT, MSG_PRIORITY_CRITICAL,
                                 fix->timestamp, payload_len);

    buf[offset++] = trigger;

    int32_t lat = (int32_t)(fix->latitude * 1e7);
    int32_t lon = (int32_t)(fix->longitude * 1e7);
    memcpy(buf + offset, &lat, 4); offset += 4;
    memcpy(buf + offset, &lon, 4); offset += 4;

    buf[offset++] = (uint8_t)(fix->speed_kmh);
    uint16_t heading = (uint16_t)(fix->heading_deg);
    memcpy(buf + offset, &heading, 2); offset += 2;

    return append_crc(buf, offset);
}

size_t codec_encode_heartbeat(uint8_t battery_pct, const gnss_fix_t *fix,
                              uint8_t *buf, size_t buf_len)
{
    if (buf == NULL) {
        return 0;
    }

    /* Payload: battery(1) + lat(4) + lon(4) + satellites(1) = 10 bytes */
    uint8_t payload_len = 10;
    size_t total_size = HEADER_SIZE + payload_len + CRC_SIZE;

    if (buf_len < total_size) {
        return 0;
    }

    uint32_t ts = fix ? fix->timestamp : 0;
    size_t offset = write_header(buf, MSG_TYPE_HEARTBEAT, MSG_PRIORITY_LOW,
                                 ts, payload_len);

    buf[offset++] = battery_pct;

    if (fix) {
        int32_t lat = (int32_t)(fix->latitude * 1e7);
        int32_t lon = (int32_t)(fix->longitude * 1e7);
        memcpy(buf + offset, &lat, 4); offset += 4;
        memcpy(buf + offset, &lon, 4); offset += 4;
        buf[offset++] = fix->satellites;
    } else {
        memset(buf + offset, 0, 9);
        offset += 9;
    }

    return append_crc(buf, offset);
}

hal_status_t codec_decode_downlink(const uint8_t *data, size_t len,
                                   msg_type_t *msg_type,
                                   const uint8_t **payload, uint8_t *pay_len)
{
    if (data == NULL || len < HEADER_SIZE + CRC_SIZE) {
        return HAL_INVALID_PARAM;
    }

    /* Verify CRC over everything except the last 2 bytes */
    size_t msg_len = len - CRC_SIZE;
    uint16_t computed = crc16_compute(data, msg_len);
    uint16_t received = ((uint16_t)data[msg_len] << 8) | data[msg_len + 1];

    if (computed != received) {
        return HAL_ERROR;
    }

    /* Parse header */
    const uplink_header_t *hdr = (const uplink_header_t *)data;

    if (msg_type) {
        *msg_type = (msg_type_t)hdr->msg_type;
    }
    if (payload) {
        *payload = data + HEADER_SIZE;
    }
    if (pay_len) {
        *pay_len = hdr->payload_len;
    }

    return HAL_OK;
}
