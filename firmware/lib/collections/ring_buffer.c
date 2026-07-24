/**
 * @file ring_buffer.c
 * @brief Generic circular buffer implementation
 */

#include "collections/ring_buffer.h"
#include <string.h>

void ring_buffer_init(ring_buffer_t *rb, uint8_t *buffer, size_t item_size, size_t capacity)
{
    if (rb == NULL || buffer == NULL || item_size == 0 || capacity == 0) {
        return;
    }

    rb->buffer = buffer;
    rb->item_size = item_size;
    rb->capacity = capacity;
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
}

bool ring_buffer_push(ring_buffer_t *rb, const void *item)
{
    if (rb == NULL || item == NULL) {
        return false;
    }

    bool overwritten = false;

    /* Copy item to head position */
    memcpy(rb->buffer + (rb->head * rb->item_size), item, rb->item_size);
    rb->head = (rb->head + 1) % rb->capacity;

    if (rb->count == rb->capacity) {
        /* Buffer full: advance tail (overwrite oldest) */
        rb->tail = (rb->tail + 1) % rb->capacity;
        overwritten = true;
    } else {
        rb->count++;
    }

    return overwritten;
}

bool ring_buffer_pop(ring_buffer_t *rb, void *item)
{
    if (rb == NULL || item == NULL || rb->count == 0) {
        return false;
    }

    memcpy(item, rb->buffer + (rb->tail * rb->item_size), rb->item_size);
    rb->tail = (rb->tail + 1) % rb->capacity;
    rb->count--;

    return true;
}

bool ring_buffer_peek(const ring_buffer_t *rb, void *item)
{
    if (rb == NULL || item == NULL || rb->count == 0) {
        return false;
    }

    memcpy(item, rb->buffer + (rb->tail * rb->item_size), rb->item_size);
    return true;
}

size_t ring_buffer_count(const ring_buffer_t *rb)
{
    if (rb == NULL) {
        return 0;
    }
    return rb->count;
}

bool ring_buffer_is_empty(const ring_buffer_t *rb)
{
    if (rb == NULL) {
        return true;
    }
    return rb->count == 0;
}

bool ring_buffer_is_full(const ring_buffer_t *rb)
{
    if (rb == NULL) {
        return false;
    }
    return rb->count == rb->capacity;
}

void ring_buffer_clear(ring_buffer_t *rb)
{
    if (rb == NULL) {
        return;
    }
    rb->head = 0;
    rb->tail = 0;
    rb->count = 0;
}
