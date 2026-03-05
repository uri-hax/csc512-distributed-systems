#include <stdio.h>

/* This file contains a copy of func_MATCH to test cross-file cloning */

void func_MATCH() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}

void func_UNIQUE() {
    // specific to this file
    int x = 100;
}
