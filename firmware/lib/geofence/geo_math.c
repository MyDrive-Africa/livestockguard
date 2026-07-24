/**
 * @file geo_math.c
 * @brief Geographic math: equirectangular distance, bearing, conversions
 */

#include "geofence/geo_math.h"
#include <math.h>

/** Earth radius in metres */
#define EARTH_RADIUS_M  6371000UL

/** Conversion factor: degrees * 1e7 to radians */
#define DEG1E7_TO_RAD   (M_PI / 1800000000.0)

/** Conversion factor: 1e-7 degrees to metres at equator */
#define DEG1E7_TO_M     (0.0111320)  /* ~111.32 km / 1e7 * 1000 */

uint32_t geo_distance_m(const geo_point_t *a, const geo_point_t *b)
{
    if (a == NULL || b == NULL) {
        return 0;
    }

    /* Equirectangular approximation
     * dx = (lon2 - lon1) * cos(mid_lat)
     * dy = (lat2 - lat1)
     * d  = sqrt(dx^2 + dy^2) * R
     */
    double dlat = (double)(b->latitude - a->latitude);
    double dlon = (double)(b->longitude - a->longitude);

    /* Mid latitude for cosine correction */
    double mid_lat_rad = ((double)(a->latitude + b->latitude) / 2.0) * DEG1E7_TO_RAD;
    double cos_lat = cos(mid_lat_rad);

    /* Convert to metres */
    double dy = dlat * DEG1E7_TO_M;
    double dx = dlon * DEG1E7_TO_M * cos_lat;

    double dist = sqrt(dx * dx + dy * dy);
    return (uint32_t)(dist + 0.5);
}

uint16_t geo_bearing(const geo_point_t *a, const geo_point_t *b)
{
    if (a == NULL || b == NULL) {
        return 0;
    }

    double dlat = (double)(b->latitude - a->latitude);
    double dlon = (double)(b->longitude - a->longitude);

    double mid_lat_rad = ((double)(a->latitude + b->latitude) / 2.0) * DEG1E7_TO_RAD;
    double cos_lat = cos(mid_lat_rad);

    double dy = dlat;
    double dx = dlon * cos_lat;

    double bearing_rad = atan2(dx, dy);
    double bearing_deg = bearing_rad * (180.0 / M_PI);

    if (bearing_deg < 0.0) {
        bearing_deg += 360.0;
    }

    return (uint16_t)(bearing_deg + 0.5);
}

geo_point_t geo_from_double(double lat, double lon)
{
    geo_point_t p;
    p.latitude = (int32_t)(lat * 1e7);
    p.longitude = (int32_t)(lon * 1e7);
    return p;
}

double geo_to_lat_double(const geo_point_t *point)
{
    if (point == NULL) {
        return 0.0;
    }
    return (double)point->latitude / 1e7;
}

double geo_to_lon_double(const geo_point_t *point)
{
    if (point == NULL) {
        return 0.0;
    }
    return (double)point->longitude / 1e7;
}
