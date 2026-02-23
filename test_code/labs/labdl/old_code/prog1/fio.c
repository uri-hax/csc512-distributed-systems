#include <stdio.h>
#include "fio.h"

// open an existing file for reading
FILE* openFile(const char* filename) {
    FILE* file = fopen(filename, "r");
    if (file == NULL) {
        perror("Error opening file");
    }
    return file;
}

/* implement the two function below */

// create a new file for writing
FILE* createFile(const char* filename) {
    FILE* file = fopen(filename, "w"); // Open file in write mode (creates a new file)
    if (file == NULL) {
        perror("Error creating file"); // Print an error message if file creation fails
    }
    return file; // Return the FILE pointer
}

// write data to an open file
 /* This function writes the provided string `data` to the specified file.
 * It flushes the file buffer after writing to ensure data is written to disk.
 */
void writeToFile(FILE* file, const char* data) {
    if (file == NULL || data == NULL) {
        fprintf(stderr, "Error: Invalid file or data in writeToFile.\n");
        return;
    }

    fprintf(file, "%s", data);  // Write data to the file
    fflush(file);  // Ensure the data is written to disk
}