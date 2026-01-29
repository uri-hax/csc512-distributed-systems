#include "lib/trie.h"
#include <stdio.h>

int main(const int argc, const char* const argv[]) {
    trie_t trie = trie_new();
    size_t bytes = 0;
    char* buf = NULL;

    // Only print lines that have not been seen before.
    while(getline(&buf, &bytes, stdin) > 0) {
        // TODO: strip newline from buffer.
        if (trie_contains(&trie, buf)) continue;
        printf("%s", buf);
        trie_insert(&trie, buf);
        free(buf);
        buf = NULL;
    }
}