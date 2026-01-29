#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// struct for a binary search tree node
typedef struct TreeNode {
    char *word;
    struct TreeNode *left;
    struct TreeNode *right;
} TreeNode;

// insert a word into the binary search tree
TreeNode* insert(TreeNode *root, char *word) {
    if (root == NULL) {
        TreeNode *newNode = (TreeNode*)malloc(sizeof(TreeNode));
        newNode->word = strdup(word);
        newNode->left = newNode->right = NULL;
        return newNode;
    }
    
    int cmp = strcmp(word, root->word);
    if (cmp < 0) {
        root->left = insert(root->left, word);
    } else if (cmp > 0) {
        root->right = insert(root->right, word);
    }
    
    return root;
}

// is the word in the binary search tree?
int contains(TreeNode *root, char *word) {
    if (root == NULL) {
        return 0;
    }
    
    int cmp = strcmp(word, root->word);
    if (cmp < 0) {
        return contains(root->left, word);
    } else if (cmp > 0) {
        return contains(root->right, word);
    } else {
        return 1;
    }
}

// free the memory used by the binary search tree
void freeTree(TreeNode *root) {
    if (root == NULL) {
        return;
    }
    
    freeTree(root->left);
    freeTree(root->right);
    free(root->word);
    free(root);
}

int main() {
    char buffer[1024];
    TreeNode *root = NULL; // initialize binary search tree

    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        if (!contains(root, buffer)) {
            root = insert(root, buffer);
            printf("%s", buffer);
        }
    }

    // Free memory used by the binary search tree
    freeTree(root);

    return 0;
}
