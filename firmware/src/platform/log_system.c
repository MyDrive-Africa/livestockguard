/**
 * @file log_system.c
 * @brief Simple UART logging implementation
 */

#include "platform/log_system.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

/* Forward declaration: platform provides UART write */
extern void hal_uart_write(const char *data, size_t len);

static const char *level_prefix[] = {
    "[???] ",
    "[ERR] ",
    "[WRN] ",
    "[INF] ",
    "[DBG] ",
};

void log_init(void)
{
    /* UART initialization handled by platform BSP */
}

void log_output(int level, const char *file, int line, const char *fmt, ...)
{
#ifdef NDEBUG
    /* No-op in release builds */
    (void)level; (void)file; (void)line; (void)fmt;
#else
    if (level > LOG_LEVEL) {
        return;
    }

    char buf[128];
    int offset = 0;

    /* Level prefix */
    const char *pfx = (level >= 1 && level <= 4) ? level_prefix[level] : level_prefix[0];
    offset += snprintf(buf + offset, sizeof(buf) - offset, "%s", pfx);

    /* Short filename (strip path) */
    const char *short_file = strrchr(file, '/');
    short_file = short_file ? (short_file + 1) : file;
    offset += snprintf(buf + offset, sizeof(buf) - offset, "%s:%d ", short_file, line);

    /* User message */
    va_list args;
    va_start(args, fmt);
    offset += vsnprintf(buf + offset, sizeof(buf) - offset, fmt, args);
    va_end(args);

    /* Newline */
    if (offset < (int)(sizeof(buf) - 1)) {
        buf[offset++] = '\n';
    }

    hal_uart_write(buf, (size_t)offset);
#endif
}
