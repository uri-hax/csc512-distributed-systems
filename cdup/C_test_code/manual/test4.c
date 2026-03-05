#include <stdio.h>

/* Test 1: basic pointer read/write */
int deref_write(int *p, int val) {
    *p = val;
    return *p;
}

/* Test 2: out-parameter (swap) */
void swap(int *a, int *b) {
    int tmp = *a;
    *a = *b;
    *b = tmp;
}

/* Test 3: pointer arithmetic over array */
int sum_via_ptr(int *arr, int n) {
    int sum = 0;
    int *p = arr;
    int *end = arr + n;
    while (p < end) {
        sum += *p;
        p++;
    }
    return sum;
}

/* Test 4: pointer to pointer (double indirection) */
void set_via_pp(int **pp, int val) {
    **pp = val;
}

/* Test 5: malloc / free */
int sum_heap(int n) {
    int *arr = (int *)malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) {
        arr[i] = i + 1;
    }
    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }
    free(arr);
    return sum;
}

/* Test 6: NULL check */
int safe_deref(int *p) {
    if (p == NULL) {
        return -1;
    }
    return *p;
}

/* Test 7: string via char* */
int str_len(char *s) {
    int len = 0;
    while (*s != '\0') {
        len++;
        s++;
    }
    return len;
}

int main() {
    /* Test 1 */
    int x = 10;
    int r1 = deref_write(&x, 42);
    printf("deref_write: x=%d r=%d\n", x, r1);

    /* Test 2 */
    int a = 3;
    int b = 7;
    swap(&a, &b);
    printf("swap: a=%d b=%d\n", a, b);

    /* Test 3 */
    int arr[5] = {1, 2, 3, 4, 5};
    int r3 = sum_via_ptr(arr, 5);
    printf("sum_via_ptr: %d\n", r3);

    /* Test 4 */
    int y = 0;
    int *py = &y;
    set_via_pp(&py, 99);
    printf("set_via_pp: y=%d\n", y);

    /* Test 5 */
    int r5 = sum_heap(4);
    printf("sum_heap: %d\n", r5);

    /* Test 6 */
    int z = 5;
    printf("safe_deref(NULL)=%d safe_deref(&z)=%d\n",
           safe_deref(NULL), safe_deref(&z));

    /* Test 7 */
    char *s = "hello";
    printf("str_len: %d\n", str_len(s));

    return 0;
}