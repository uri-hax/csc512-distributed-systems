#include <stdio.h>

int sum_array(int arr[], int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += arr[i];
    }
    return total;
}

int sum_scores(int scores[], int count) {
    int result = 0;
    for (int j = 0; j < count; j++) {
        result += scores[j];
    }
    return result;
}

int max_array(int arr[], int n) {
    int best = arr[0];
    for (int i = 1; i < n; i++) {
        if (arr[i] > best) {
            best = arr[i];
        }
    }
    return best;
}

int main() {
    int data[5] = {3, 1, 4, 1, 5};
    int grades[5] = {90, 85, 78, 92, 88};
    int s1 = sum_array(data, 5);
    int s2 = sum_scores(grades, 5);
    int m = max_array(data, 5);
    return 0;
}