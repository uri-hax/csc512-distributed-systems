/*
 * Demonstrates graceful degradation under memory pressure.
 *
 * Key technique: reads its own cgroup memory limit before each allocation
 * and stops voluntarily before the kernel OOM-killer fires.
 *
 * Expected behavior under memory_ceiling (64 MB):
 *   - Allocates chunks until within SAFETY_MB of the cgroup limit
 *   - Prints an error to stderr
 *   - Frees all memory
 *   - Exits with code 1 (not 137)
 *
 * What analyze_failure should report:
 *   - Non-zero exit but NOT oom_killed
 *   - stderr contains error message → GOOD: graceful error handling
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>

#define CHUNK_MB     4
#define CHUNK_BYTES  (CHUNK_MB * 1024 * 1024)
#define MAX_CHUNKS   200
#define SAFETY_MB    20

static double elapsed_s(struct timespec start) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - start.tv_sec)
         + (now.tv_nsec - start.tv_nsec) / 1e9;
}

/* Read the current cgroup memory limit in MB.
 * Tries cgroup v2 first (/sys/fs/cgroup/memory.max),
 * then cgroup v1 (/sys/fs/cgroup/memory/memory.limit_in_bytes).
 * Returns -1 if the limit cannot be read (no container / unlimited). */
static long get_limit_mb(void) {
    FILE *f = fopen("/sys/fs/cgroup/memory.max", "r");
    if (!f) f = fopen("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r");
    if (!f) return -1;

    char buf[32];
    if (!fgets(buf, sizeof(buf), f)) { fclose(f); return -1; }
    fclose(f);

    /* cgroup v2 reports "max" when unlimited */
    if (strncmp(buf, "max", 3) == 0) return -1;

    long bytes = atol(buf);
    /* v1 reports a very large number when unlimited */
    if (bytes > (long)1e12) return -1;
    return bytes / (1024 * 1024);
}

static void cleanup_and_exit(char **chunks, int count, int code, const char *reason) {
    fprintf(stderr, "ERROR: %s — freeing %d chunks and exiting.\n", reason, count);
    for (int i = 0; i < count; i++) {
        free(chunks[i]);
        chunks[i] = NULL;
    }
    fprintf(stderr, "Cleanup complete. Exiting with code %d.\n", code);
    fflush(stderr);
    exit(code);
}

int main(void) {
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);

    printf("=== Graceful Fail Demo ===\n");
    printf("Will detect memory pressure via cgroup and exit cleanly.\n\n");
    fflush(stdout);

    char *chunks[MAX_CHUNKS];
    memset(chunks, 0, sizeof(chunks));
    int allocated = 0;

    while (elapsed_s(start) < 60.0) {
        if (allocated >= MAX_CHUNKS)
            cleanup_and_exit(chunks, allocated, 1, "reached internal chunk limit");

        /* Check cgroup limit before allocating */
        long limit_mb  = get_limit_mb();
        long current_mb = (long)allocated * CHUNK_MB;

        if (limit_mb > 0 && current_mb + CHUNK_MB + SAFETY_MB > limit_mb) {
            fprintf(stderr,
                "ERROR: memory limit approaching — used %ld MB, "
                "limit %ld MB, safety margin %d MB\n",
                current_mb, limit_mb, SAFETY_MB);
            cleanup_and_exit(chunks, allocated, 1, "memory limit approached");
        }

        char *p = malloc(CHUNK_BYTES);
        if (!p) {
            fprintf(stderr, "ERROR: malloc failed at chunk %d: %s\n",
                    allocated, strerror(errno));
            cleanup_and_exit(chunks, allocated, 1, "malloc returned NULL");
        }

        memset(p, allocated & 0xFF, CHUNK_BYTES);
        chunks[allocated++] = p;

        printf("[%.1fs] Chunk %d allocated — total: %ld MB",
               elapsed_s(start), allocated, current_mb + CHUNK_MB);
        if (limit_mb > 0)
            printf("  (limit: %ld MB)", limit_mb);
        printf("\n");
        fflush(stdout);

        sleep(1);
    }

    printf("\n[%.1fs] Time limit reached. Cleaning up.\n", elapsed_s(start));
    for (int i = 0; i < allocated; i++) free(chunks[i]);
    printf("=== Exited cleanly after %d MB allocated ===\n", allocated * CHUNK_MB);
    return 0;
}