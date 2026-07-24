/**
 * @file track_module.h
 * @brief Position tracking and buffering module
 */
#ifndef TRACK_MODULE_H
#define TRACK_MODULE_H

#include "hal_types.h"
#include "services/config_service.h"

/**
 * @brief Initialize the track module and position buffer
 */
void track_module_init(void);

/**
 * @brief Record a new position to the ring buffer
 * @param fix  GNSS fix to record
 */
void track_module_record_position(const gnss_fix_t *fix);

/**
 * @brief Get the number of buffered positions
 * @return Number of positions in the buffer
 */
uint16_t track_module_get_buffer_count(void);

/**
 * @brief Get a batch of position records for transmission
 * @param records   Output array
 * @param max_count Maximum records to retrieve
 * @return Number of records copied
 */
uint8_t track_module_get_batch(position_record_t *records, uint8_t max_count);

#endif /* TRACK_MODULE_H */
