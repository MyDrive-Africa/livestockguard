# Platform configuration: nRF9160 Collar
# Full-featured cellular collar with solar charging

set(FEATURE_CELLULAR      ON CACHE BOOL "" FORCE)
set(FEATURE_BLE           ON CACHE BOOL "" FORCE)
set(FEATURE_SOLAR         ON CACHE BOOL "" FORCE)
set(FEATURE_VIRTUAL_FENCE ON CACHE BOOL "" FORCE)
set(FEATURE_OTA           ON CACHE BOOL "" FORCE)

set(MAX_GEOFENCES       8    CACHE STRING "Maximum number of geofences" FORCE)
set(POSITION_BUFFER_SIZE 4096 CACHE STRING "Position ring buffer size" FORCE)
