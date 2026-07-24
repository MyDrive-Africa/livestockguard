/**
 * @file point_in_polygon.c
 * @brief Ray-casting algorithm using int64 arithmetic for microdegree coordinates
 */

#include "geofence/point_in_polygon.h"
#include "geofence/geo_math.h"

bool point_in_polygon(const geo_point_t *point, const geo_point_t *polygon, uint8_t n)
{
    if (n < 3 || point == NULL || polygon == NULL) {
        return false;
    }

    bool inside = false;
    uint8_t j = n - 1;

    for (uint8_t i = 0; i < n; i++) {
        int64_t yi = (int64_t)polygon[i].latitude;
        int64_t yj = (int64_t)polygon[j].latitude;
        int64_t xi = (int64_t)polygon[i].longitude;
        int64_t xj = (int64_t)polygon[j].longitude;
        int64_t py = (int64_t)point->latitude;
        int64_t px = (int64_t)point->longitude;

        /* Check if ray from point crosses this edge */
        if (((yi > py) != (yj > py)) &&
            (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
        j = i;
    }

    return inside;
}

bool point_in_circle(const geo_point_t *point, const geo_point_t *centre, uint32_t radius_m)
{
    if (point == NULL || centre == NULL) {
        return false;
    }

    uint32_t distance = geo_distance_m(point, centre);
    return distance <= radius_m;
}
