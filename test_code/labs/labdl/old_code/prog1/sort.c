#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINES 1000   // Maximum number of lines we can store
#define MAX_LENGTH 1024   // Maximum length of each line

// Merge function for Merge Sort
void merge(char arr[MAX_LINES][MAX_LENGTH], int left, int mid, int right) {
    int leftSize = mid - left + 1; // Calculate sizes of two halves
    int rightSize = right - mid; // Calculate sizes of two halves

    // Temporary arrays
    char leftArr[leftSize][MAX_LENGTH], rightArr[rightSize][MAX_LENGTH];

    // Copy data to temp arrays
    for (int i = 0; i < leftSize; i++) 
        strcpy(leftArr[i], arr[left + i]);  // Copy left half
    for (int j = 0; j < rightSize; j++) 
        strcpy(rightArr[j], arr[mid + 1 + j]); // Copy right half

    // Merge the two halves
    int i = 0, j = 0, k = left;
    while (i < leftSize && j < rightSize) {
        if (strcmp(leftArr[i], rightArr[j]) <= 0) {
            strcpy(arr[k++], leftArr[i++]);  // Copy smaller element
        } else {
            strcpy(arr[k++], rightArr[j++]); // Copy smaller element
        }
    }

    // Copy remaining elements, if any
    while (i < leftSize) strcpy(arr[k++], leftArr[i++]); 
    while (j < rightSize) strcpy(arr[k++], rightArr[j++]); 
}

// Merge Sort function
void mergeSort(char arr[MAX_LINES][MAX_LENGTH], int left, int right) {
    if (left < right) {
        int mid = left + (right - left) / 2; // Calculate mid point
        mergeSort(arr, left, mid); // Sort first half
        mergeSort(arr, mid + 1, right); // Sort second half
        merge(arr, left, mid, right); // Merge the sorted halves
    }
}

int main() {
    char lines[MAX_LINES][MAX_LENGTH];  // Array to store input lines
    int count = 0; // Counter to track the number of lines read

    // Read input lines from stdin until we reach MAX_LINES or EOF
    while (count < MAX_LINES && fgets(lines[count], MAX_LENGTH, stdin) != NULL) {
        // Remove the newline character from the input line (if present)
        lines[count][strcspn(lines[count], "\n")] = '\0';
        count++; // Increment line counter
    }

    // Sort the lines using Merge Sort
    mergeSort(lines, 0, count - 1);

    // Print the sorted lines to stdout
    for (int i = 0; i < count; i++) {
        printf("%s\n", lines[i]);  // Print each sorted line followed by a newline
    }

    return 0; // Return success
}
