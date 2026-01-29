#include <string.h>
#include "trie.h"

void test_trie() {
    trie_t trie = trie_new();

    trie_insert(&trie, "abc");
    assert(trie_contains(&trie, "abc"));
    assert(!trie_contains(&trie, "cd"));
    assert(!trie_contains(&trie, "ab"));
    assert(!trie_contains(&trie, "abcd"));

    trie_insert(&trie, "cd");
    assert(trie_contains(&trie, "abc"));
    assert(trie_contains(&trie, "cd"));
    assert(!trie_contains(&trie, "ab"));
    assert(!trie_contains(&trie, "abcd"));

    trie_insert(&trie, "ab");
    assert(trie_contains(&trie, "abc"));
    assert(trie_contains(&trie, "cd"));
    assert(trie_contains(&trie, "ab"));
    assert(!trie_contains(&trie, "abcd"));

    trie_insert(&trie, "abcd");
    assert(trie_contains(&trie, "abc"));
    assert(trie_contains(&trie, "cd"));
    assert(trie_contains(&trie, "ab"));
    assert(trie_contains(&trie, "abcd"));

    trie_delete(&trie);
}

int main(const int argc, const char* const argv[]) {
    test_trie();
}