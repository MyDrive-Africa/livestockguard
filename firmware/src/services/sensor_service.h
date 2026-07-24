#ifndef SENSOR_SERVICE_H
#define SENSOR_SERVICE_H
#include "hal_types.h"
void sensor_service_init(void);
void sensor_service_read_accel(accel_data_t *data);
float sensor_service_get_magnitude(void);
bool sensor_service_motion_detected(void);
#endif
