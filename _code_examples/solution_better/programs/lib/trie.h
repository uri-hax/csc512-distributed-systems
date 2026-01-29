#ifndef H_TRIE
#define H_TRIE

#include <stdlib.h>
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct trie_node {
    struct trie_node* children[256];
} trie_node_t_;

typedef struct trie {
    trie_node_t_* root;
} trie_t;

trie_node_t_* trie_node_new_() {
    trie_node_t_* node = (trie_node_t_*)malloc(sizeof(trie_node_t_));
    node->children[0] = (trie_node_t_*)0;
    for(int i = 1; i < 256; ++i)
        node->children[i] = NULL;
    return node;
}

trie_t trie_new() {
    trie_t trie;
    trie.root = NULL;
    return trie;
}

void trie_node_delete_(trie_node_t_* node) {
    if (node == NULL) return;
    for (int i = 1; i < 256; ++i)
        trie_node_delete_(node->children[i]);
    free(node);
}

void trie_delete(trie_t* trie) {
    trie_node_delete_(trie->root);
    trie->root = NULL;
}

trie_node_t_* trie_node_insert_(trie_node_t_* node, const char* const s) {
    if (s[0] == '\0') return node;

    if (node == NULL)
        node = trie_node_new_();

    node->children[(uint8_t)s[0]] = trie_node_insert_(node->children[(uint8_t)s[0]], s + 1);
    if (s[1] == '\0')
        node->children[0] = (trie_node_t_*)1;
    return node;
}

void trie_insert(trie_t* trie, const char* const s) {
    assert(s[0] != '\0');
    trie->root = trie_node_insert_(trie->root, s);
}

bool trie_node_contains_(trie_node_t_* node, const char* const s) {
    assert(s[0] != '\0');
    if (node == NULL) 
        return false;
    if (s[1] == '\0')
        return (uintptr_t)node->children[0] & 1;
    return trie_node_contains_(node->children[(uint8_t)s[0]], s + 1);
}

bool trie_contains(trie_t* trie, const char* const s) {
    assert(s[0] != '\0');
    return trie_node_contains_(trie->root, s);
}

#endif