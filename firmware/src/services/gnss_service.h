#ifndef GNSS_SERVICE_H
#define GNSS_SERVICE_H
#include "hal_types.h"
void gnss_service_init(void);
bool gnss_service_acquire_fix(void);
void gnss_service_get_last_fix(gnss_fix_t *fix);
#endif
