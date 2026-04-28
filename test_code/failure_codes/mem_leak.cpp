/* memory_leak.cpp
 *
 * Student implementation of a simple log processing pipeline.
 * Reads "log entries" in a loop, parses them into records,
 * and maintains a history buffer for analysis.
 *
 * The memory bugs are the kind a student would accidentally write:
 *
 *   BUG 1 — LogRecord is allocated with new inside process_entry()
 *            but the caller stores raw pointers in a vector and never
 *            deletes them. The student forgot that storing a pointer
 *            doesn't transfer ownership.
 *
 *   BUG 2 — parse_fields() allocates a char* buffer for each field
 *            and returns it. The caller uses it and drops it — no delete[].
 *            Classic C-style allocation in a C++ program.
 *
 *   BUG 3 — When the history buffer is "flushed" (every 30 entries),
 *            the student clears the vector but forgets to delete the
 *            objects first — the pointers are gone but the heap memory
 *            is not freed.
 *
 *   BUG 4 — FILE* opened for each "batch" but only closed on the
 *            happy path — error returns skip fclose().
 *
 * Under cpu_gradual the program slows down but keeps leaking.
 * Under memory profiles it eventually gets OOM-killed with no cleanup.
 * There is no graceful handling anywhere.
 */

#include <iostream>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <ctime>
#include <unistd.h>

static const int HISTORY_FLUSH = 30;   /* flush every N entries */
static const int FIELD_BUF_KB  = 64;   /* size of each field buffer */
static const int RUN_SECONDS   = 60;

static double elapsed_s(struct timespec t0) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - t0.tv_sec) + (now.tv_nsec - t0.tv_nsec) / 1e9;
}

/* ── Data types a student might write ───────────────────────────────────── */

struct LogRecord {
    int    id;
    char   level[16];
    char   message[256];
    char  *raw_line;      /* heap allocated, student forgot to free */
};

/* BUG 2: returns heap-allocated buffer, caller responsible for delete[]
 * but callers never do */
static char *parse_fields(const char *input, int field_index) {
    char *buf = new char[FIELD_BUF_KB * 1024];
    const char *tokens[] = {"INFO", "WARN", "ERROR", "DEBUG"};
    snprintf(buf, FIELD_BUF_KB * 1024, "%s:field%d:%s",
             input, field_index, tokens[field_index % 4]);
    return buf;
}

/* BUG 1: allocates LogRecord with new, returns raw pointer.
 * Caller stores it in a vector<LogRecord*> and never deletes it. */
static LogRecord *process_entry(int id) {
    LogRecord *rec = new LogRecord();
    rec->id = id;

    /* BUG 2 in action: parse_fields result used and dropped */
    char *field = parse_fields("log_entry", id % 4);
    snprintf(rec->level,   sizeof(rec->level),   "%s", "INFO");
    snprintf(rec->message, sizeof(rec->message), "processed entry %d: %.40s", id, field);
    /* field is leaked here — student used it but forgot delete[] field */

    rec->raw_line = new char[512];
    snprintf(rec->raw_line, 512, "RAW[%d] timestamp=%ld", id, (long)time(nullptr));

    return rec;
}

/* BUG 3: "flushes" history by clearing the vector but not deleting objects */
static void flush_history(std::vector<LogRecord*> &history) {
    /* Student thinks this frees memory — it only frees the vector's
     * internal pointer array, not the LogRecord objects on the heap */
    history.clear();
}

int main() {
    struct timespec t0;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    std::cout << "Log processor starting." << std::endl;

    std::vector<LogRecord*> history;
    int entry_id  = 0;
    int batch_num = 0;

    while (elapsed_s(t0) < RUN_SECONDS) {
        /* BUG 4: FILE* opened each batch, only closed on success path */
        FILE *batch_log = fopen("/dev/null", "w");

        for (int i = 0; i < 10; i++) {
            LogRecord *rec = process_entry(entry_id++);
            history.push_back(rec);

            fprintf(batch_log, "entry %d: %s\n", rec->id, rec->message);

            std::cout << "[" << elapsed_s(t0) << "s]"
                      << "  entry=" << rec->id
                      << "  history=" << history.size()
                      << "  msg=" << rec->message
                      << std::endl;

            /* Simulate work proportional to entry size */
            volatile long sum = 0;
            for (int j = 0; j < 500000; j++) sum += j;
        }

        /* BUG 4: fclose only reached if we get here — an exception or
         * signal above would skip this */
        fclose(batch_log);
        batch_num++;

        if ((int)history.size() >= HISTORY_FLUSH) {
            std::cout << "[" << elapsed_s(t0) << "s]"
                      << "  Flushing history (" << history.size()
                      << " records)..." << std::endl;
            flush_history(history);  /* BUG 3: leaks all LogRecord objects */
            std::cout << "  Done. History size: " << history.size() << std::endl;
        }

        sleep(1);
    }

    std::cout << "Done. Processed " << entry_id << " entries." << std::endl;
    /* BUG 1+3: history still contains unflushed pointers, never deleted
     * BUG 2: all parse_fields buffers leaked throughout
     * No cleanup whatsoever */
    return 0;
}