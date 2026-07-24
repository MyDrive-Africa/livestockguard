/**
 * @file ota_module.h
 * @brief Over-the-air update module
 */
#ifndef OTA_MODULE_H
#define OTA_MODULE_H

#include "hal_types.h"

/** OTA state machine states */
typedef enum {
    OTA_STATE_IDLE,
    OTA_STATE_CHECKING,
    OTA_STATE_DOWNLOADING,
    OTA_STATE_VERIFYING,
    OTA_STATE_APPLYING,
    OTA_STATE_COMPLETE,
    OTA_STATE_ERROR,
} ota_state_t;

/**
 * @brief Initialize the OTA module
 */
void ota_module_init(void);

/**
 * @brief Process OTA state machine (call repeatedly while in OTA state)
 * @return Current OTA state after processing
 */
ota_state_t ota_module_process(void);

/**
 * @brief Check if an OTA update is available
 * @return true if an update is pending
 */
bool ota_module_is_available(void);

#endif /* OTA_MODULE_H */
