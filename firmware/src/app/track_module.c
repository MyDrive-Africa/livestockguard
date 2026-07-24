/**
 * @file track_module.c
 * @brief Position tracking and buffering implementation
 */

#include "app/track_module.h"
#include "collections/ring_buffer.h"
#include "platform/log_system.h"

#include <string.h>

#ifndef POSITION_BUFFER_SIZE
#define POSITION_BUFFER_SIZE 256
#endif

static ring_buffer_t g_position_buffer;
static position_record_t g_storage[POSITION_BUFFER_SIZE];
static geo_point_t g_reference_point;
static bool g_has_reference;

void track_module_init(void)
{
    ring_buffer_init(&g_position_buffer, (uint8_t *)g_storage,
                     sizeof(position_record_t), POSITION_BUFFER_SIZE);
    memset(&g_reference_point, 0, sizeof(g_reference_point));
    g_has_reference = false;
    LOG_INFO("Track module initialized (buffer=%d)", POSITION_BUFFER_SIZE);
}

void track_module_record_position(const gnss_fix_t *fix)
{
    int32_t lat_i = (int32_t)(fix->latitude * 1e7);
    int32_t lon_i = (int32_t)(fix->longitude * 1e7);

    /* Set reference on first fix */
    if (!g_has_reference) {
        g_reference_point.latitude = lat_i;
        g_reference_point.longitude = lon_i;
        g_has_reference = true;
    }

    position_record_t rec = {
        .timestamp  = fix->timestamp,
        .lat_offset = lat_i - g_reference_point.latitude,
        .lon_offset = lon_i - g_reference_point.longitude,
        .speed      = (uint8_t)(fix->speed_kmh < 255.0f ? fix->speed_kmh : 255),
        .heading    = (uint8_t)(fix->heading_deg * 255.0f / 360.0f),
        .hdop_x10   = (uint8_t)(fix->hdop * 10.0f),
        .flags      = fix->fix_quality,
    };

    ring_buffer_push(&g_position_buffer, &rec);
}

uint16_t track_module_get_buffer_count(void)
{
    return (uint16_t)ring_buffer_count(&g_position_buffer);
}

uint8_t track_module_get_batch(position_record_t *records, uint8_t max_count)
{
    uint8_t count = 0;
    while (count < max_count) {
        if (!ring_buffer_pop(&g_position_buffer, &records[count])) {
            break;
        }
        count++;
    }
    return count;
}
