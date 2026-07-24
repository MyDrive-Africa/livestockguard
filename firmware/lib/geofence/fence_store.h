/**
 * @file fence_store.h
 * @brief Geofence persistent storage interface
 */
#ifndef FENCE_STORE_H
#define FENCE_STORE_H

#include "hal_types.h"
#include "app/fence_module.h"

/**
 * @brief Initialize the fence store
 */
void fence_store_init(void);

/**
 * @brief Load all geofences from non-volatile storage
 * @param fences    Output array
 * @param max_count Maximum fences to load
 * @return Number of fences loaded
 */
uint8_t fence_store_load(geofence_def_t *fences, uint8_t max_count);

/**
 * @brief Save a geofence to non-volatile storage
 * @param fence  Geofence definition to save
 * @return HAL_OK on success
 */
hal_status_t fence_store_save(const geofence_def_t *fence);

/**
 * @brief Delete a geofence from non-volatile storage
 * @param fence_id  ID of geofence to delete
 * @return HAL_OK on success
 */
hal_status_t fence_store_delete(uint8_t fence_id);

/**
 * @brief Get number of stored geofences
 * @return Count of stored fences
 */
uint8_t fence_store_count(void);

/**
 * @brief Persist all in-memory fences to non-volatile storage
 * @param fences    Array of geofences
 * @param count     Number of fences to persist
 * @return HAL_OK on success
 */
hal_status_t fence_store_persist(const geofence_def_t *fences, uint8_t count);

#endif /* FENCE_STORE_H */
