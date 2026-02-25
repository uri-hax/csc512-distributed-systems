#include <stdio.h>
#include <stdlib.h>

void printNum(int arr[], int size) {
    int i;
    for (i = 0; i < size; i++) {
        printf("%d\n", arr[i]);
    }
}

int main(int argc, char *argv[]) {
    int size = argc - 1;
    int *num = (int *)malloc(size * sizeof(int));
    for (int i = 0; i < size; i++) {
        num[i] = atoi(argv[i + 1]);
    }
    printNum(num, size);

    free(num);
    return 0;
}