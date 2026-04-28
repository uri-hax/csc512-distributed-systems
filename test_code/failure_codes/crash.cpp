/* 
 * Demonstrates ungraceful C++ failure modes that produce meaningful output.
 * Failures are triggered deterministically by time, not by running out of memory,
 * so chaos profiles affect performance output rather than masking the crash.
 *
 * Phase 1 (0–20s):  Normal allocation and work — produces output every second
 * Phase 2 (20–25s): Heap corruption via out-of-bounds write — SIGABRT (134)
 *                   triggered on the next allocation after the corrupt write
 * Phase 3:          Never reached — but would trigger double-delete
 *
 * Expected failure modes:
 *   any profile     → SIGABRT (134) at ~20s from heap corruption
 *   memory profiles → may OOM-kill (137) before phase 2 if memory is very tight
 *
 * What analyze_failure should report:
 *   - exit 134 / SIGABRT
 *   - stderr contains glibc heap error ("corrupted" or "invalid")
 *   - No error message from the program itself before dying
 */

#include <iostream>
#include <cstring>
#include <ctime>
#include <unistd.h>

static const int CHUNK_MB    = 8;
static const int CHUNK_BYTES = CHUNK_MB * 1024 * 1024;
static const int MAX_CHUNKS  = 20;

static double elapsed_s(struct timespec start) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - start.tv_sec)
         + (now.tv_nsec - start.tv_nsec) / 1e9;
}

int main() {
    struct timespec start;
    clock_gettime(CLOCK_MONOTONIC, &start);

    std::cout << "=== C++ Crash Demo ===" << std::endl;
    std::cout << "Phase 1: normal allocation (20s)" << std::endl;
    std::cout << "Phase 2: heap corruption triggered at 20s → expect SIGABRT\n" << std::endl;

    char *chunks[MAX_CHUNKS];
    std::memset(chunks, 0, sizeof(chunks));
    int count = 0;

    /* ── Phase 1: normal work for 20 seconds ─────────────────────────────── */
    while (elapsed_s(start) < 20.0) {
        if (count < MAX_CHUNKS) {
            /* No try/catch — bad_alloc would terminate() uncaught */
            char *p = new char[CHUNK_BYTES];
            std::memset(p, count & 0xFF, CHUNK_BYTES);
            chunks[count++] = p;
        }

        /* Busy work so CPU chaos is visible in timing */
        volatile double x = 1.0;
        for (int i = 0; i < 1000000; i++) x *= 1.0000001;

        std::cout << "[" << elapsed_s(start) << "s]"
                  << "  chunks: " << count
                  << "  (" << count * CHUNK_MB << " MB)"
                  << "  x=" << x   /* prevents optimisation */
                  << std::endl;
        sleep(1);
    }

    /* ── Phase 2: deliberate heap corruption ──────────────────────────────── */
    std::cout << "\n[" << elapsed_s(start) << "s] Phase 2: writing past buffer end..." << std::endl;

    if (count > 0) {
        /* Write one byte past the allocated end of chunk 0.
         * This corrupts glibc's heap metadata for the adjacent chunk.
         * The corruption is detected on the NEXT heap operation (new/delete),
         * which calls abort() → SIGABRT (exit 134). */
        chunks[0][CHUNK_BYTES] = 0xDE;

        std::cout << "[" << elapsed_s(start) << "s] Corruption written. "
                  << "Triggering detection with next allocation..." << std::endl;

        /* This new triggers glibc's heap consistency check → SIGABRT */
        char *trigger = new char[1024];
        trigger[0] = 0;   /* never reached */
        delete[] trigger;
    }

    /* ── Phase 3: never reached ───────────────────────────────────────────── */
    std::cout << "Attempting cleanup..." << std::endl;
    for (int i = 0; i < count; i++) delete[] chunks[i];
    delete[] chunks[0];   /* double-delete if we somehow got here */

    return 0;
}