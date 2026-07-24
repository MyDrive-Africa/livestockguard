/**
 * @file nv_store.c
 * @brief Non-volatile storage implementation using internal flash
 */

#include "platform/nv_store.h"
#include "platform/log_system.h"

#include <string.h>

/* Memory map: each key gets a fixed 4KB region in flash */
#define NV_FLASH_BASE   0x000F0000
#define NV_PAGE_SIZE    4096

/* Forward declarations for platform-specific flash HAL */
extern hal_status_t hal_flash_read(uint32_t addr, void *data, size_t len);
extern hal_status_t hal_flash_write(uint32_t addr, const void *data, size_t len);
extern hal_status_t hal_flash_erase_page(uint32_t addr);

static inline uint32_t nv_key_address(nv_key_t key)
{
    return NV_FLASH_BASE + ((uint32_t)key * NV_PAGE_SIZE);
}

void nv_store_init(void)
{
    /* Verify flash is accessible by reading first page header */
    uint32_t magic;
    hal_status_t status = hal_flash_read(NV_FLASH_BASE, &magic, sizeof(magic));
    if (status == HAL_OK) {
        LOG_INFO("NV store initialized");
    } else {
        LOG_ERROR("NV store flash not accessible");
    }
}

hal_status_t nv_store_read(nv_key_t key, void *data, size_t len)
{
    if (key >= NV_KEY_MAX || !data || len == 0) {
        return HAL_INVALID_PARAM;
    }

    uint32_t addr = nv_key_address(key);
    if (len > NV_PAGE_SIZE) {
        return HAL_INVALID_PARAM;
    }

    return hal_flash_read(addr, data, len);
}

hal_status_t nv_store_write(nv_key_t key, const void *data, size_t len)
{
    if (key >= NV_KEY_MAX || !data || len == 0) {
        return HAL_INVALID_PARAM;
    }

    uint32_t addr = nv_key_address(key);
    if (len > NV_PAGE_SIZE) {
        return HAL_INVALID_PARAM;
    }

    hal_status_t status = hal_flash_erase_page(addr);
    if (status != HAL_OK) {
        LOG_ERROR("Flash erase failed at 0x%08lX", (unsigned long)addr);
        return status;
    }

    status = hal_flash_write(addr, data, len);
    if (status != HAL_OK) {
        LOG_ERROR("Flash write failed at 0x%08lX", (unsigned long)addr);
    }
    return status;
}
