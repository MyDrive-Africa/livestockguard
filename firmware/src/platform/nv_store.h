#ifndef NV_STORE_H
#define NV_STORE_H
#include "hal_types.h"
typedef enum { NV_KEY_CONFIG, NV_KEY_GEOFENCES, NV_KEY_POSITION_BUFFER, NV_KEY_DEVICE_ID, NV_KEY_MAX } nv_key_t;
void nv_store_init(void);
hal_status_t nv_store_read(nv_key_t key, void *data, size_t len);
hal_status_t nv_store_write(nv_key_t key, const void *data, size_t len);
#endif
