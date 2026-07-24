#ifndef COMMS_SERVICE_H
#define COMMS_SERVICE_H
#include "hal_types.h"
void comms_service_init(void);
void comms_service_transmit_queue(void);
void comms_service_send_immediate(void);
void comms_service_check_downlink(void);
bool comms_service_has_critical(void);
bool comms_service_batch_interval_elapsed(void);
bool comms_service_buffer_nearly_full(void);
bool comms_service_panic_cancelled(void);
#endif
