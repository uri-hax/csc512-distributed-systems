#include <stdio.h>

int clamp(int val, int lo, int hi) {
    if (val < lo) {
        val = lo;
    } else if (val > hi) {
        val = hi;
    }
    return val;
}

int sum_range(int arr[], int n, int lo, int hi) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        int clamped = clamp(arr[i], lo, hi);
        total += clamped;
    }
    return total;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};
    int lo = 15;
    int hi = 35;
    int result = sum_range(data, 5, lo, hi);
    printf("Result: %d\n", result);
    return 0;
}