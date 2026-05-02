/* matrix_multiply.c
 * Student implementation of matrix multiplication benchmark.
 *
 * Bugs:
 *   - Naive O(n^3) — no cache blocking, devastating under CPU throttle
 *   - No timeout awareness — just runs slower and slower
 *   - No graceful handling of slowdown
 *
 * Under cpu_gradual (5s steps): iter/s drops visibly each step
 * Under cpu_spike:  iter/s alternates high/low every 4s
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 128

static double now_s() {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

int main() {
    printf("Matrix multiply %dx%d benchmark\n\n", N, N);
    fflush(stdout);

    double *A = malloc(N * N * sizeof(double));
    double *B = malloc(N * N * sizeof(double));
    double *C = malloc(N * N * sizeof(double));

    if (!A || !B || !C) {
        fprintf(stderr, "ERROR: malloc failed\n");
        return 1;
    }

    for (int i = 0; i < N * N; i++) {
        A[i] = (double)(i % 100) / 100.0;
        B[i] = (double)((i * 3) % 100) / 100.0;
        C[i] = 0.0;
    }

    double start        = now_s();
    double window_start = start;
    int    total_iters  = 0;
    int    window_iters = 0;

    while (now_s() - start < 30.0) {
        memset(C, 0, N * N * sizeof(double));

        for (int i = 0; i < N; i++)
            for (int j = 0; j < N; j++) {
                double sum = 0.0;
                for (int k = 0; k < N; k++)
                    sum += A[i*N+k] * B[k*N+j];
                C[i*N+j] = sum;
            }

        total_iters++;
        window_iters++;

        double now     = now_s();
        double elapsed = now - window_start;
        if (elapsed >= 1.0) {
            printf("t=%.1fs  iterations/sec: %.1f  total: %d\n",
                   now - start,
                   window_iters / elapsed,
                   total_iters);
            fflush(stdout);
            window_start = now;
            window_iters = 0;
        }
    }

    double total = now_s() - start;
    printf("\nCompleted %d iterations in %.1fs (avg %.1f/s)\n",
           total_iters, total, total_iters / total);

    free(A); free(B); free(C);
    return 0;
}