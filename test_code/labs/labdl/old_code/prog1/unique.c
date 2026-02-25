#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LENGTH 1024  // Max length of each word

int main() {
    char current[MAX_LENGTH];  // Store the current word
    char previous[MAX_LENGTH] = "";  // Store the previous word for comparison

    // Read words from stdin
    while (fgets(current, sizeof(current), stdin) != NULL) {
        current[strcspn(current, "\n")] = '\0'; // Remove newline character

        // Print the word only if it is different from the previous word
        if (strcmp(current, previous) != 0) {
            printf("%s\n", current);
            strcpy(previous, current);  // Update previous word
        }
    }

    return 0;
}

