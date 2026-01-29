#include "../fio/fio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINES 3010
#define MAX_LINE_LENGTH 1000

int main() {
    char buffer[1024];
    char *dict[MAX_LINES] = {NULL}; // in case we choose to add more words

    FILE *dict_file = openFile("unix_dict.text");
    
    int i = 0; // read data from unix_dict.text and store words in array
    while (fgets(buffer, sizeof(buffer), dict_file) != NULL && i < MAX_LINES) {
        size_t buff_len = strlen(buffer);
        int pos = buff_len - 1;
        // remove newline character, if present
        if (buffer[pos] == '\n') {
            buffer[pos] = '\0';
        }
        dict[i] = strdup(buffer);
        i++;
    }

    // Read data from stdin and write it to stdout (standard output)
    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        // Remove newline character, if present
        if (buffer[strlen(buffer) - 1] == '\n') {
            buffer[strlen(buffer) - 1] = '\0';
        }

        // Check if the word is present in the array
        int found = 0;
        for (int n = 0; n < i; n++) {
            if (strcmp(buffer, dict[n]) == 0) {
                found = 1;
                break;
            }
        }

        // If not found, print it to stdout
        if (!found) {
            printf("%s\n", buffer);
        }
    }

    // team up to clean up!
    fclose(dict_file);
    //free(dict);

    return 0;
}