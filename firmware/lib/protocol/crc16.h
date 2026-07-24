/**
 * @file crc16.h
 * @brief CRC-16/CCITT (polynomial 0x1021) interface
 */
#ifndef CRC16_H
#define CRC16_H

#include <stdint.h>
#include <stddef.h>

/**
 * @brief Compute CRC-16/CCITT over a data buffer
 * @param data  Pointer to data
 * @param len   Length in bytes
 * @return 16-bit CRC value
 */
uint16_t crc16_compute(const uint8_t *data, size_t len);

/**
 * @brief Update running CRC-16 with a single byte
 * @param crc   Current CRC value
 * @param byte  New byte to include
 * @return Updated CRC value
 */
uint16_t crc16_update(uint16_t crc, uint8_t byte);

#endif /* CRC16_H */
