/**
 * @file sensor_service.c
 * @brief Accelerometer data service implementation
 */

#include "services/sensor_service.h"
#include "hal_accel.h"
#include "platform/log_system.h"

#include <math.h>
#include <string.h>

#define SAMPLE_BUFFER_SIZE 32

static accel_data_t g_samples[SAMPLE_BUFFER_SIZE];
static uint8_t g_sample_count;
static float g_magnitude_avg;
static float g_variance;

void sensor_service_init(void)
{
    hal_accel_config_t cfg = {
        .sample_rate        = HAL_ACCEL_RATE_25HZ,
        .range              = HAL_ACCEL_RANGE_4G,
        .fifo_enabled       = true,
        .fifo_watermark     = 16,
        .wakeup_enabled     = true,
        .wakeup_threshold_mg = 50,
    };
    hal_accel_init(&cfg);
    memset(g_samples, 0, sizeof(g_samples));
    g_sample_count = 0;
    g_magnitude_avg = 0.0f;
    g_variance = 0.0f;
    LOG_INFO("Sensor service initialized");
}

void sensor_service_read_accel(accel_data_t *data)
{
    if (hal_accel_read(data) == HAL_OK) {
        /* Store in circular sample buffer */
        g_samples[g_sample_count % SAMPLE_BUFFER_SIZE] = *data;
        g_sample_count++;

        /* Recompute magnitude and variance over recent samples */
        uint8_t n = (g_sample_count < SAMPLE_BUFFER_SIZE) ? g_sample_count : SAMPLE_BUFFER_SIZE;
        float sum = 0.0f;
        float sum_sq = 0.0f;
        for (uint8_t i = 0; i < n; i++) {
            float x = g_samples[i].x / 1000.0f;
            float y = g_samples[i].y / 1000.0f;
            float z = g_samples[i].z / 1000.0f;
            float mag = sqrtf(x * x + y * y + z * z);
            sum += mag;
            sum_sq += mag * mag;
        }
        g_magnitude_avg = sum / n;
        g_variance = (sum_sq / n) - (g_magnitude_avg * g_magnitude_avg);
    }
}

float sensor_service_get_magnitude(void)
{
    /* Compute magnitude from latest sample in g */
    uint8_t idx = (g_sample_count > 0) ? ((g_sample_count - 1) % SAMPLE_BUFFER_SIZE) : 0;
    float x = g_samples[idx].x / 1000.0f;
    float y = g_samples[idx].y / 1000.0f;
    float z = g_samples[idx].z / 1000.0f;
    return sqrtf(x * x + y * y + z * z);
}

bool sensor_service_motion_detected(void)
{
    return g_variance > 0.01f;
}
