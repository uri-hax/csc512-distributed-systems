#include <stdio.h>
#include <string.h>

// Realistic challenge: struct type (parser should create a struct segment)
typedef struct {
    int x;
    int y;
} Point;

// Challenge: multiple return paths, nested conditions
int compare_points(Point a, Point b) {
    int dx = a.x - b.x;
    int dy = a.y - b.y;
    if (dx == 0) {
        if (dy == 0) {
            return 0;
        } else {
            return dy;
        }
    } else {
        return dx;
    }
}

// Challenge: while loop instead of for, pointer param, compound assigns
int dot_product(int *u, int *v, int n) {
    int sum = 0;
    int i = 0;
    while (i < n) {
        sum += u[i] * v[i];
        i++;
    }
    return sum;
}

// Challenge: nested for loops, multiple loop iterators
int matrix_trace(int mat[][4], int n) {
    int trace = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == j) {
                trace += mat[i][j];
            }
        }
    }
    return trace;
}

// Challenge: do-while loop
int count_digits(int n) {
    int count = 0;
    if (n == 0) {
        return 1;
    }
    if (n < 0) {
        n = -n;
    }
    do {
        count++;
        n /= 10;
    } while (n > 0);
    return count;
}

int main() {
    Point p1 = {3, 4};
    Point p2 = {3, 7};
    int cmp = compare_points(p1, p2);

    int u[3] = {1, 2, 3};
    int v[3] = {4, 5, 6};
    int dot = dot_product(u, v, 3);

    int mat[4][4] = {
        {1, 0, 0, 0},
        {0, 2, 0, 0},
        {0, 0, 3, 0},
        {0, 0, 0, 4}
    };
    int tr = matrix_trace(mat, 4);

    int digits = count_digits(12345);

    printf("cmp=%d dot=%d trace=%d digits=%d\n", cmp, dot, tr, digits);
    return 0;
}