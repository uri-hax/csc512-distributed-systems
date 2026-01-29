#include "../fio/fio.h"
#include <stdio.h>
#include <stdlib.h>

int main() {
    char buffer[1024]; // buffer to store data

    FILE *file;
    char filename[] = "unix_sentence.text"; 

    // open the file in read mode
    file = openFile(filename);

    if (file == NULL) {
        perror("ERROR: File opening failed");
        return 1; // Exit with an error code
    }

    // Read and print the contents of the file
    while (fgets(buffer, sizeof(buffer), file) != NULL) {
        fputs(buffer, stdout);
    }


    // Close the file
    fclose(file);

    return 0;
}