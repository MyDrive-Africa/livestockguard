cmake_minimum_required(VERSION 3.20)
project(livestockguard_firmware VERSION 1.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Platform selection
set(PLATFORM "nrf9160_collar" CACHE STRING "Target platform")
set_property(CACHE PLATFORM PROPERTY STRINGS
    nrf9160_collar
    nrf52840_eartag
    stm32wle5_collar
    esp32s3_retrofit
)

# Feature flags (defaults OFF, enabled by platform cmake)
option(FEATURE_CELLULAR      "Enable cellular connectivity"    OFF)
option(FEATURE_LORAWAN       "Enable LoRaWAN connectivity"     OFF)
option(FEATURE_BLE           "Enable BLE connectivity"         OFF)
option(FEATURE_VIRTUAL_FENCE "Enable on-device virtual fence"  OFF)
option(FEATURE_OTA           "Enable over-the-air updates"     OFF)

# Include platform-specific configuration
include(${CMAKE_CURRENT_SOURCE_DIR}/platforms/${PLATFORM}/platform.cmake)

# Source files
set(FIRMWARE_SOURCES
    src/main.c
    src/app/fence_module.c
    lib/geofence/point_in_polygon.c
    lib/geofence/geo_math.c
    lib/protocol/crc16.c
    lib/protocol/message_codec.c
    lib/collections/ring_buffer.c
)

# Include directories
set(FIRMWARE_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/hal/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/lib
    ${CMAKE_CURRENT_SOURCE_DIR}
)

add_executable(${PROJECT_NAME} ${FIRMWARE_SOURCES})
target_include_directories(${PROJECT_NAME} PRIVATE ${FIRMWARE_INCLUDES})

# Compiler flags
target_compile_options(${PROJECT_NAME} PRIVATE
    -Wall
    -Wextra
    -Os
    -ffunction-sections
    -fdata-sections
)

# Linker flags to remove unused sections
target_link_options(${PROJECT_NAME} PRIVATE
    -Wl,--gc-sections
)

# Pass feature flags as compile definitions
if(FEATURE_CELLULAR)
    target_compile_definitions(${PROJECT_NAME} PRIVATE FEATURE_CELLULAR=1)
endif()
if(FEATURE_LORAWAN)
    target_compile_definitions(${PROJECT_NAME} PRIVATE FEATURE_LORAWAN=1)
endif()
if(FEATURE_BLE)
    target_compile_definitions(${PROJECT_NAME} PRIVATE FEATURE_BLE=1)
endif()
if(FEATURE_VIRTUAL_FENCE)
    target_compile_definitions(${PROJECT_NAME} PRIVATE FEATURE_VIRTUAL_FENCE=1)
endif()
if(FEATURE_OTA)
    target_compile_definitions(${PROJECT_NAME} PRIVATE FEATURE_OTA=1)
endif()

# Platform-specific definitions
target_compile_definitions(${PROJECT_NAME} PRIVATE
    MAX_GEOFENCES=${MAX_GEOFENCES}
    POSITION_BUFFER_SIZE=${POSITION_BUFFER_SIZE}
    PLATFORM_${PLATFORM}=1
)
