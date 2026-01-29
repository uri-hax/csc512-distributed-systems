#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* makewords(const char* input) {
    if (input == NULL) {
        fprintf(stderr, "ERROR: linebreaker function string input for processing is NULL.\n");
        exit(1);
    }

    char target = ' ';
    const char* replace = "\n";

    size_t inputLen = strlen(input);
    size_t replaceLen = strlen(replace);

    // calculate the maximum possible length of the result
    size_t maxLen = inputLen + (inputLen * (replaceLen - 1)) + 1;


    char* result = (char*)malloc(inputLen); // allocate memory for the result
    if (result == NULL) {
        fprintf(stderr, "ERROR: memory allocation failed in linebreaker.\n");
        exit(1);
    }

    size_t resultIndex = 0;

    for (size_t i = 0; i < inputLen; i++) {
        if (input[i] == target) {
            // replace the target character with the replacement string
            for (size_t n = 0; n < replaceLen; n++) {
                result[resultIndex++] = replace[n];
                // check if we exceed the maximum length
                if (resultIndex >= maxLen - 1) {
                    break;
                }
            }
        } else {
            // copy the character as is
            result[resultIndex++] = input[i];
        }

        // ensure we don't exceed the maximum length
        if (resultIndex >= maxLen - 1) {
            break;
        }
    }

    // null-terminate the result
    result[resultIndex] = '\0';

    return result;
}

void removePercentFromEnd(char *input) {
    if (input == NULL) {
        fprintf(stderr, "ERROR: Input string is NULL.\n");
        return;
    }

    int length = strlen(input);

    // Start from the end of the string and move backward
    for (int i = length - 1; i >= 0; i--) {
        if (input[i] == '%') {
            input[i] = '\n'; // Replace '%' with null terminator
        } else {
            break; // Stop when a non-'%' character is encountered
        }
    }
}


int main() {
    // creates a 1024 byte buffer to store data, will this be enough memory to store data?
    char buffer[1024];

    // Read data from stdin and write it to stdout (standard output)
    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        // pass data from the buffer to a function convert spaces to linebreaks
        char* result = makewords(buffer);
        removePercentFromEnd(result);
        fputs(result, stdout);
        free(result);
    }

    return 0;
}