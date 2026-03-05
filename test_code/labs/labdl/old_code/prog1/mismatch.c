#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_WORDS 3100   // Maximum number of words in dictionary
#define MAX_LENGTH 1024   // Maximum length of each word

/**
 * Loads dictionary words from a file into an array.
 */
int loadDictionary(const char *filename, char dict[MAX_WORDS][MAX_LENGTH]) {
    FILE *file = fopen(filename, "r");  // Open dictionary file for reading
    if (!file) {
        fprintf(stderr, "Error: Could not open dictionary file %s\n", filename);
        exit(1);  // Exit if the dictionary file is missing or inaccessible
    }

    int count = 0;  // Keep track of how many words are stored
    while (count < MAX_WORDS && fgets(dict[count], MAX_LENGTH, file)) {
        dict[count][strcspn(dict[count], "\n")] = '\0'; // Remove trailing newline
        count++;
    }

    fclose(file);  // Close dictionary file after loading words
    return count;  // Return the total number of words loaded into memory
}

/**
 * Checks if a given word exists in the dictionary.
 */
int isInDictionary(const char *word, char dict[MAX_WORDS][MAX_LENGTH], int dict_size) {
    for (int i = 0; i < dict_size; i++) {
        if (strcmp(word, dict[i]) == 0) {  // Compare input word with dictionary words
            return 1;  // Word is found in the dictionary
        }
    }
    return 0;  // Word is missing from the dictionary
}

int main() {
    char dict[MAX_WORDS][MAX_LENGTH];  // Array to store dictionary words
    int dict_size = loadDictionary("unix_dict.text", dict);  // Load dictionary into memory

    char buffer[MAX_LENGTH];  // Buffer to hold input words from stdin

    // Read words from stdin and check against the dictionary
    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        buffer[strcspn(buffer, "\n")] = '\0'; // Remove newline character

        // If the word is NOT found in the dictionary, print it to stdout
        if (!isInDictionary(buffer, dict, dict_size)) {
            printf("%s\n", buffer);
        }
    }

    return 0;  // Return success
}
