#include <stdio.h>

/* We use identical function names to ensure strict Type I cloning.
   This would not compile, but matches the definition of Type I clone. */

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}
