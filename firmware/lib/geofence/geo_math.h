/**
 * @file geo_math.h
 * @brief Geographic math utilities for geofencing
 */
#ifndef GEO_MATH_H
#define GEO_MATH_H

#include "hal_types.h"

/**
 * @brief Calculate equirectangular distance between two points
 * @param a First point (degrees * 1e7)
 * @param b Second point (degrees * 1e7)
 * @return Distance in metres
 */
uint32_t geo_distance_m(const geo_point_t *a, const geo_point_t *b);

/**
 * @brief Calculate bearing from point a to point b
 * @param a Origin point (degrees * 1e7)
 * @param b Destination point (degrees * 1e7)
 * @return Bearing in degrees (0-359)
 */
uint16_t geo_bearing(const geo_point_t *a, const geo_point_t *b);

/**
 * @brief Convert double lat/lon to geo_point_t
 * @param lat  Latitude in degrees
 * @param lon  Longitude in degrees
 * @return geo_point_t with values scaled to 1e7
 */
geo_point_t geo_from_double(double lat, double lon);

/**
 * @brief Convert geo_point_t latitude to double degrees
 */
double geo_to_lat_double(const geo_point_t *point);

/**
 * @brief Convert geo_point_t longitude to double degrees
 */
double geo_to_lon_double(const geo_point_t *point);

#endif /* GEO_MATH_H */
