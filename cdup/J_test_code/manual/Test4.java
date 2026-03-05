/**
 * Test4.java — Java port of test4.c
 * Java doesn't have raw pointers, so pointer patterns are mapped to:
 *   - int[] wrappers for pass-by-reference scalars  (deref_write, swap)
 *   - int[]   for heap arrays                       (sum_heap)
 *   - int[][] for double-pointer                    (set_via_pp)
 *   - null check for safe_deref
 *   - char[] / String for str_len
 *
 * The IR clone detector should still find structural similarity to test4.c
 * because the op-on-variable DAG patterns are identical.
 */
public class Test4 {

    // --- deref_write ---
    // C: void deref_write(int *p, int val) { *p = val; return *p; }
    // Java: write val into p[0], return p[0]
    static int deref_write(int[] p, int val) {
        p[0] = val;
        return p[0];
    }

    // --- swap ---
    // C: void swap(int *a, int *b) { int tmp = *a; *a = *b; *b = tmp; }
    // Java: swap via int[] wrappers
    static void swap(int[] a, int[] b) {
        int tmp = a[0];
        a[0] = b[0];
        b[0] = tmp;
    }

    // --- sum_via_ptr ---
    // C: int sum_via_ptr(int *arr, int n)
    // Java: same algorithm, direct array
    static int sum_via_ptr(int[] arr, int n) {
        int sum = 0;
        for (int i = 0; i < n; i++) {
            sum += arr[i];
        }
        return sum;
    }

    // --- set_via_pp ---
    // C: void set_via_pp(int **pp, int val) { **pp = val; }
    // Java: pp[0][0] = val
    static void set_via_pp(int[][] pp, int val) {
        pp[0][0] = val;
    }

    // --- sum_heap ---
    // C: int sum_heap(int n) { int *arr = malloc(...); for(...) arr[i]=i+1; ... }
    // Java: allocate array on heap (which is always the case in Java)
    static int sum_heap(int n) {
        int[] arr = new int[n];
        for (int i = 0; i < n; i++) {
            arr[i] = i + 1;
        }
        int sum = 0;
        for (int i = 0; i < n; i++) {
            sum += arr[i];
        }
        return sum;
    }

    // --- safe_deref ---
    // C: int safe_deref(int *p) { if (p == NULL) return -1; return *p; }
    // Java: null check on Integer wrapper
    static int safe_deref(Integer p) {
        if (p == null) {
            return -1;
        }
        return p;
    }

    // --- str_len ---
    // Java: iterate char array until null terminator equivalent
    static int str_len(char[] s) {
        int len = 0;
        int i = 0;
        while (s[i] != '\0') {
            len++;
            i++;
        }
        return len;
    }

    public static void main(String[] args) {
        // deref_write
        int[] x = {10};
        int r = deref_write(x, 42);
        System.out.println("deref_write: x=" + x[0] + " r=" + r);

        // swap
        int[] av = {3};
        int[] bv = {7};
        swap(av, bv);
        System.out.println("swap: a=" + av[0] + " b=" + bv[0]);

        // sum_via_ptr
        int[] nums = {1, 2, 3, 4, 5};
        int s = sum_via_ptr(nums, 5);
        System.out.println("sum_via_ptr: " + s);

        // set_via_pp
        int[] y = {0};
        int[][] pp = {y};
        set_via_pp(pp, 99);
        System.out.println("set_via_pp: y=" + y[0]);

        // sum_heap
        int sh = sum_heap(4);
        System.out.println("sum_heap: " + sh);

        // safe_deref
        int sd_null = safe_deref(null);
        int z = 5;
        int sd_val = safe_deref(z);
        System.out.println("safe_deref(null)=" + sd_null + " safe_deref(z)=" + sd_val);

        // str_len
        char[] hello = {'h', 'e', 'l', 'l', 'o', '\0'};
        int sl = str_len(hello);
        System.out.println("str_len: " + sl);
    }
}