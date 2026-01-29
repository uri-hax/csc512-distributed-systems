#include <stdio.h>
#include "lib/trie.h"
#include "../fio/fio.h"

// This code is also not great. Static and heap allocated buffers are used 
// inconsistently. Same goes for fgets and getline.

int main(const int argc, const char* const argv[]) {
    // Load the dictionary into a trie.
    trie_t trie = trie_new();
    FILE* file = fio_open("unix_dict.text");
    char word[4096];
    while (fgets(word, sizeof(word) / sizeof(word[0]), file) > 0)
        trie_insert(&trie, word);

    // Print lines on stdin that are not in the trie.
    size_t bytes = 0;
    char* buf = NULL;
    while(getline(&buf, &bytes, stdin) > 0) {
        // TODO: strip newline from buffer.
        if (trie_contains(&trie, buf)) continue;
        printf("%s", buf);
        free(buf);
        buf = NULL;
    }
}