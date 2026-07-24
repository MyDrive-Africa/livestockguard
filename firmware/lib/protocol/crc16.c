/**
 * @file crc16.c
 * @brief CRC-16/CCITT implementation (polynomial 0x1021, init 0xFFFF)
 */

#include "protocol/crc16.h"

uint16_t crc16_update(uint16_t crc, uint8_t byte)
{
    crc ^= (uint16_t)byte << 8;
    for (uint8_t i = 0; i < 8; i++) {
        if (crc & 0x8000) {
            crc = (crc << 1) ^ 0x1021;
        } else {
            crc <<= 1;
        }
    }
    return crc;
}

uint16_t crc16_compute(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;

    if (data == NULL) {
        return crc;
    }

    for (size_t i = 0; i < len; i++) {
        crc = crc16_update(crc, data[i]);
    }

    return crc;
}
