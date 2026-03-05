package cdup.cross_lang_test_code;

/*
 * GradeBook.java — A student grade tracking system.
 *
 * Clone targets (paired with stats.c):
 *
 *   TYPE I:   computeTotal / computeTotalDuplicate  (exact copy within Java)
 *   TYPE II:  findHighestScore / findLowestScore     (same structure, renamed)
 *   TYPE III: sortByScore ↔ C selection_sort          (same algo + swap counter)
 *             curveScores ↔ C normalize               (similar scaling with offset)
 *             countPassing ↔ C count_above_threshold  (same pattern, diff constant)
 *   TYPE IV:  computeAverage ↔ C compute_mean         (same accumulate-then-divide)
 *             lookupStudent ↔ C binary_search          (same binary search skeleton)
 *             findHighestScore ↔ C find_max            (same scan pattern)
 */

public class GradeBook {

    /* ---------- Accumulator: total ---------- */

    public static int computeTotal(int scores[], int n) {
        int total = 0;
        int i = 0;
        while (i < n) {
            total = total + scores[i];
            i = i + 1;
        }
        return total;
    }

    /* Exact copy — deliberate Type I clone within Java */
    public static int computeTotalDuplicate(int grades[], int count) {
        int total = 0;
        int i = 0;
        while (i < count) {
            total = total + grades[i];
            i = i + 1;
        }
        return total;
    }

    /* ---------- Average (Type IV pair with C compute_mean) ---------- */

    public static double computeAverage(int scores[], int n) {
        int sum = 0;
        int i = 0;
        while (i < n) {
            sum = sum + scores[i];
            i = i + 1;
        }
        double avg = (double)sum / (double)n;
        return avg;
    }

    /* ---------- Weighted average (unique to Java) ---------- */

    public static double computeWeightedAvg(int scores[], int weights[], int n) {
        int weighted_sum = 0;
        int weight_total = 0;
        int i = 0;
        while (i < n) {
            weighted_sum = weighted_sum + scores[i] * weights[i];
            weight_total = weight_total + weights[i];
            i = i + 1;
        }
        double result = (double)weighted_sum / (double)weight_total;
        return result;
    }

    /* ---------- Highest score (Type II pair with findLowest, Type IV pair with C find_max) ---------- */

    public static int findHighestScore(int scores[], int n) {
        int best = scores[0];
        int idx = 1;
        while (idx < n) {
            if (scores[idx] > best) {
                best = scores[idx];
            }
            idx = idx + 1;
        }
        return best;
    }

    /* Type II clone of findHighestScore — renamed vars, flipped comparison */
    public static int findLowestScore(int scores[], int n) {
        int worst = scores[0];
        int pos = 1;
        while (pos < n) {
            if (scores[pos] < worst) {
                worst = scores[pos];
            }
            pos = pos + 1;
        }
        return worst;
    }

    /* ---------- Sort (Type III pair with C selection_sort — adds swap counter) ---------- */

    public static int sortByScore(int scores[], int n) {
        int swaps = 0;
        int i = 0;
        while (i < n - 1) {
            int min_idx = i;
            int j = i + 1;
            while (j < n) {
                if (scores[j] < scores[min_idx]) {
                    min_idx = j;
                }
                j = j + 1;
            }
            int temp = scores[min_idx];
            scores[min_idx] = scores[i];
            scores[i] = temp;
            swaps = swaps + 1;
            i = i + 1;
        }
        return swaps;
    }

    /* ---------- Binary search (Type IV pair with C binary_search) ---------- */

    public static int lookupStudent(int sorted_ids[], int n, int target_id) {
        int low = 0;
        int high = n - 1;
        while (low <= high) {
            int mid = (low + high) / 2;
            if (sorted_ids[mid] == target_id) {
                return mid;
            }
            if (sorted_ids[mid] < target_id) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }
        return -1;
    }

    /* ---------- Count passing (Type III pair with C count_above_threshold) ---------- */

    public static int countPassing(int scores[], int n) {
        int count = 0;
        int i = 0;
        while (i < n) {
            if (scores[i] >= 60) {
                count = count + 1;
            }
            i = i + 1;
        }
        return count;
    }

    /* ---------- Curve scores (Type III pair with C normalize) ---------- */

    public static void curveScores(int scores[], int n) {
        int max_val = findHighestScore(scores, n);
        int min_val = findLowestScore(scores, n);
        int range = max_val - min_val;
        int bonus = 10;
        int i = 0;
        while (i < n) {
            scores[i] = (scores[i] - min_val) * 100 / range + bonus;
            i = i + 1;
        }
    }

    /* ---------- Compute letter grades (unique to Java) ---------- */

    public static void assignLetterGrades(int scores[], char grades[], int n) {
        int i = 0;
        while (i < n) {
            if (scores[i] >= 90) {
                grades[i] = 'A';
            } else if (scores[i] >= 80) {
                grades[i] = 'B';
            } else if (scores[i] >= 70) {
                grades[i] = 'C';
            } else if (scores[i] >= 60) {
                grades[i] = 'D';
            } else {
                grades[i] = 'F';
            }
            i = i + 1;
        }
    }

    /* ---------- Main: process a class ---------- */

    public static void main(String[] args) {
        int scores[] = new int[8];
        scores[0] = 45;
        scores[1] = 82;
        scores[2] = 67;
        scores[3] = 91;
        scores[4] = 38;
        scores[5] = 73;
        scores[6] = 55;
        scores[7] = 60;

        int n = 8;
        int total = computeTotal(scores, n);
        double avg = computeAverage(scores, n);
        int highest = findHighestScore(scores, n);
        int lowest = findLowestScore(scores, n);
        int passing = countPassing(scores, n);

        int swaps = sortByScore(scores, n);
        int found = lookupStudent(scores, n, 67);

        System.out.println("total=" + total + " avg=" + (int)avg +
            " high=" + highest + " low=" + lowest +
            " passing=" + passing + " found_at=" + found);
    }
}