/*
 * stats.c — A small statistics library for numeric arrays.
 *
 * Clone targets (paired with GradeBook.java):
 *
 *   TYPE I:   compute_sum / compute_sum_copy  (exact duplicate within C)
 *   TYPE II:  find_max / find_min              (same structure, renamed vars)
 *   TYPE III: selection_sort / modified variant in Java (added/changed stmts)
 *   TYPE IV:  compute_mean ↔ Java computeAverage (same algorithm skeleton,
 *             completely different variable names, types, language)
 *             binary_search ↔ Java lookupStudent (same binary search skeleton)
 *             find_max ↔ Java findHighestScore  (same scan pattern, diff lang)
 */

/* ---------- Accumulator: sum ---------- */

int compute_sum(int arr[], int n) {
    int total = 0;
    int i = 0;
    while (i < n) {
        total = total + arr[i];
        i = i + 1;
    }
    return total;
}

/* Exact copy of compute_sum — deliberate Type I clone */
int compute_sum_copy(int data[], int count) {
    int total = 0;
    int i = 0;
    while (i < count) {
        total = total + data[i];
        i = i + 1;
    }
    return total;
}

/* ---------- Mean (Type IV pair with Java computeAverage) ---------- */

double compute_mean(int arr[], int n) {
    int sum = 0;
    int i = 0;
    while (i < n) {
        sum = sum + arr[i];
        i = i + 1;
    }
    double mean = (double)sum / (double)n;
    return mean;
}

/* ---------- Variance ---------- */

double compute_variance(int arr[], int n) {
    double mean = compute_mean(arr, n);
    double sum_sq = 0.0;
    int i = 0;
    while (i < n) {
        double diff = arr[i] - mean;
        sum_sq = sum_sq + diff * diff;
        i = i + 1;
    }
    return sum_sq / (double)n;
}

/* ---------- Max scan (Type II pair with find_min, Type IV pair with Java) ---------- */

int find_max(int arr[], int n) {
    int best = arr[0];
    int idx = 1;
    while (idx < n) {
        if (arr[idx] > best) {
            best = arr[idx];
        }
        idx = idx + 1;
    }
    return best;
}

/* Type II clone of find_max — same structure, renamed variables, flipped comparison */
int find_min(int arr[], int n) {
    int result = arr[0];
    int pos = 1;
    while (pos < n) {
        if (arr[pos] < result) {
            result = arr[pos];
        }
        pos = pos + 1;
    }
    return result;
}

/* ---------- Selection sort (Type III pair with Java — Java adds a swap count) ---------- */

void selection_sort(int arr[], int n) {
    int i = 0;
    while (i < n - 1) {
        int min_idx = i;
        int j = i + 1;
        while (j < n) {
            if (arr[j] < arr[min_idx]) {
                min_idx = j;
            }
            j = j + 1;
        }
        int temp = arr[min_idx];
        arr[min_idx] = arr[i];
        arr[i] = temp;
        i = i + 1;
    }
}

/* ---------- Binary search (Type IV pair with Java lookupStudent) ---------- */

int binary_search(int arr[], int n, int target) {
    int low = 0;
    int high = n - 1;
    while (low <= high) {
        int mid = (low + high) / 2;
        if (arr[mid] == target) {
            return mid;
        }
        if (arr[mid] < target) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return -1;
}

/* ---------- Count occurrences (Type III within C — similar to sum but conditional) ---------- */

int count_above_threshold(int arr[], int n, int threshold) {
    int count = 0;
    int i = 0;
    while (i < n) {
        if (arr[i] > threshold) {
            count = count + 1;
        }
        i = i + 1;
    }
    return count;
}

/* ---------- Normalise array to [0..100] (Type III pair with Java curveScores) ---------- */

void normalize(int arr[], int n) {
    int max_val = find_max(arr, n);
    int min_val = find_min(arr, n);
    int range = max_val - min_val;
    int i = 0;
    while (i < n) {
        arr[i] = (arr[i] - min_val) * 100 / range;
        i = i + 1;
    }
}

/* ---------- Main: run stats on a sample ---------- */

int main() {
    int data[8];
    data[0] = 45;
    data[1] = 82;
    data[2] = 67;
    data[3] = 91;
    data[4] = 38;
    data[5] = 73;
    data[6] = 55;
    data[7] = 60;

    int n = 8;
    int total = compute_sum(data, n);
    double avg = compute_mean(data, n);
    int hi = find_max(data, n);
    int lo = find_min(data, n);
    int above_70 = count_above_threshold(data, n, 70);

    selection_sort(data, n);
    int found = binary_search(data, n, 67);

    printf("sum=%d mean=%d max=%d min=%d above70=%d found_at=%d\n",
           total, (int)avg, hi, lo, above_70, found);

    return 0;
}