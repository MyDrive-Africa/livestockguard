#ifndef LOG_SYSTEM_H
#define LOG_SYSTEM_H
#ifndef LOG_LEVEL
#define LOG_LEVEL 3
#endif
void log_init(void);
void log_output(int level, const char *file, int line, const char *fmt, ...);
#define LOG_ERROR(fmt, ...) log_output(1, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)  log_output(2, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...)  log_output(3, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_DEBUG(fmt, ...) log_output(4, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#endif
