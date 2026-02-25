// how can we import our local fio C library?
#include <stdio.h>
#include <stdlib.h>
#include "fio.h"  // Import the local fio library

FILE *openFile(const char *filename);  // Declare the function

int main() {
    FILE *file;
    char filename[] = "unix_sentence.text"; 
    char buffer[1024]; // Buffer to store data

    // Open the file using the local fio library
    file = openFile(filename);
    if (file == NULL) {
        fprintf(stderr, "Error: Could not open file %s\n", filename);
        return 1;
    }

    // Read and print the contents of the file
    while (fgets(buffer, sizeof(buffer), file) != NULL) {
        printf("%s", buffer);  // Print the buffer directly
    }

    // Close the file
    fclose(file);
    return 0;
}