/**
 * @file ring_buffer.h
 * @brief Generic circular buffer (ring buffer)
 */
#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef struct {
    uint8_t *buffer;      /**< Backing storage */
    size_t   item_size;   /**< Size of each item in bytes */
    size_t   capacity;    /**< Maximum number of items */
    size_t   head;        /**< Write index */
    size_t   tail;        /**< Read index */
    size_t   count;       /**< Current number of items */
} ring_buffer_t;

/**
 * @brief Initialize a ring buffer
 * @param rb        Ring buffer instance
 * @param buffer    Backing memory (must be at least item_size * capacity bytes)
 * @param item_size Size of each element in bytes
 * @param capacity  Maximum number of elements
 */
void ring_buffer_init(ring_buffer_t *rb, uint8_t *buffer, size_t item_size, size_t capacity);

/**
 * @brief Push an item (overwrites oldest if full)
 * @param rb    Ring buffer
 * @param item  Pointer to item to copy in
 * @return true if an existing item was overwritten
 */
bool ring_buffer_push(ring_buffer_t *rb, const void *item);

/**
 * @brief Pop the oldest item
 * @param rb    Ring buffer
 * @param item  Destination for popped item
 * @return true on success, false if buffer is empty
 */
bool ring_buffer_pop(ring_buffer_t *rb, void *item);

/**
 * @brief Peek at the oldest item without removing it
 * @param rb    Ring buffer
 * @param item  Destination for peeked item
 * @return true on success, false if buffer is empty
 */
bool ring_buffer_peek(const ring_buffer_t *rb, void *item);

/**
 * @brief Get current number of items in buffer
 */
size_t ring_buffer_count(const ring_buffer_t *rb);

/**
 * @brief Check if buffer is empty
 */
bool ring_buffer_is_empty(const ring_buffer_t *rb);

/**
 * @brief Check if buffer is full
 */
bool ring_buffer_is_full(const ring_buffer_t *rb);

/**
 * @brief Clear all items from the buffer
 */
void ring_buffer_clear(ring_buffer_t *rb);

#endif /* RING_BUFFER_H */
