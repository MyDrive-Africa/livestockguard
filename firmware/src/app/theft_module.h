/**
 * @file theft_module.h
 * @brief Anti-theft detection module
 */
#ifndef THEFT_MODULE_H
#define THEFT_MODULE_H
#include "hal_types.h"

typedef enum { THEFT_NONE, THEFT_SUSPICIOUS, THEFT_DETECTED } theft_result_t;
typedef enum { THEFT_TRIGGER_NONE, THEFT_TRIGGER_TRANSPORT, THEFT_TRIGGER_TAMPER, THEFT_TRIGGER_NIGHT_MOVE, THEFT_TRIGGER_GEOFENCE } theft_trigger_t;

void theft_module_init(void);
theft_result_t theft_module_check(const gnss_fix_t *fix);
theft_trigger_t theft_module_get_trigger(void);
void theft_module_cancel_panic(void);
bool theft_module_is_panic_active(void);

#endif
