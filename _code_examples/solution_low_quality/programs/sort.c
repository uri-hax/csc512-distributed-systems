#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINES 3010
#define MAX_LINE_LENGTH 1000

// comparison function for qsort
int lineCmp(const void* a, const void* b) {
    return strcmp(*(const char**)a, *(const char**)b);
}

// custom insertion sort for small datasets
void insertionSort(char* lines[], int lineCount) {
    int i, j;
    char* key;

    for (i = 1; i < lineCount; i++) {
        key = lines[i];
        j = i - 1;

        while (j >= 0 && strcmp(lines[j], key) > 0) {
            lines[j + 1] = lines[j];
            j = j - 1;
        }

        lines[j + 1] = key;
    }
}

int main() {
    char* lines[MAX_LINES];
    char line[MAX_LINE_LENGTH];
    int lineCount = 0;

    // read lines from stdin and allocate memory
    while (lineCount < MAX_LINES && fgets(line, sizeof(line), stdin) != NULL) {
        lines[lineCount] = malloc(strlen(line) + 1);
        if (!lines[lineCount]) {
            fprintf(stderr, "memory allocation failed.\n");
            exit(1);
        }
        strcpy(lines[lineCount], line);
        lineCount++;
    }

    // use insertion sort for small datasets, otherwise use qsort
    insertionSort(lines, lineCount);

    // print the sorted lines
    for (int i = 0; i < lineCount; i++) {
        printf("%s", lines[i]);
        free(lines[i]);
    }

    return 0;
}