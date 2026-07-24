/**
 * @file point_in_polygon.h
 * @brief Point-in-polygon and point-in-circle tests for geofencing
 */
#ifndef POINT_IN_POLYGON_H
#define POINT_IN_POLYGON_H

#include "hal_types.h"

/**
 * @brief Ray-casting point-in-polygon test using integer arithmetic
 * @param point     Test point (microdegrees * 1e7)
 * @param polygon   Array of polygon vertices
 * @param n         Number of vertices in polygon
 * @return true if point is inside the polygon
 */
bool point_in_polygon(const geo_point_t *point, const geo_point_t *polygon, uint8_t n);

/**
 * @brief Test if a point is within a circle
 * @param point     Test point (microdegrees * 1e7)
 * @param centre    Circle centre (microdegrees * 1e7)
 * @param radius_m  Circle radius in metres
 * @return true if point is within the circle
 */
bool point_in_circle(const geo_point_t *point, const geo_point_t *centre, uint32_t radius_m);

#endif /* POINT_IN_POLYGON_H */
