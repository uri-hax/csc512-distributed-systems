#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* makewords(const char* input) {
    // calculate the maximum possible len of the result
    size_t maxLen = strlen(input) + 1;

    char* result = (char*)malloc(maxLen); // allocate memory for the result

    if (result == NULL) {
        fprintf(stderr, "ERROR: memory allocation failed in makewords.\n");
        exit(1);
    }

    // Process the input, replacing spaces with newlines
    size_t j = 0;
    for (size_t i = 0; input[i] != '\0'; i++) {
        if (input[i] == ' ') {
            result[j++] = '\n';  // Convert space to newline
        } else {
            result[j++] = input[i];
        }

    }
    result[j] = '\0'; // Proper null termination

    return result;
}


int main() {
    // creates a 1024 byte buffer to store data, will this be enough memory to store data?
    char buffer[1024]; // Buffer to store input line

    // Read data from stdin and write it to stdout (standard output)
    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        // pass data from the buffer to a function convert spaces to linebreaks
        char* result = makewords(buffer);
        fputs(result, stdout);
        free(result); // releases the memory allocated
    }

    return 0;
}
