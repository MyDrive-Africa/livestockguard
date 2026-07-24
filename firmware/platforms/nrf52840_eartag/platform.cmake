# Platform configuration: nRF52840 Ear Tag
# Low-power BLE/LoRaWAN ear tag with limited resources

set(FEATURE_LORAWAN ON CACHE BOOL "" FORCE)
set(FEATURE_BLE     ON CACHE BOOL "" FORCE)
set(FEATURE_OTA     ON CACHE BOOL "" FORCE)

set(MAX_GEOFENCES       4    CACHE STRING "Maximum number of geofences" FORCE)
set(POSITION_BUFFER_SIZE 2048 CACHE STRING "Position ring buffer size" FORCE)
