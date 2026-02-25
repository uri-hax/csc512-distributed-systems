// how can we import our local fio C library?
#include "../fio/fio.h"
#include <stdio.h>
#include <stdlib.h>

int main() {
    FILE *file;
    char filename[] = "test.txt"; 
    char buffer[1024]; // buffer to store data

    // open the file using the local fio library (Hint: see line 1)
    file = openFile(filename);

    // Read and print the contents of the file
    while (fgets(buffer, sizeof(buffer), file) != NULL) {
        // put file contents (buffer) into stdout (Hint: look at linebreaker)
        fprintf(stdout, "%s", buffer);
    }

    // Close the file
    fclose(file);

    return 0;
}