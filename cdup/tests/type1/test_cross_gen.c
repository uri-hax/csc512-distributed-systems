#include <stdio.h>

void parent_func() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
    
    // extra parent stuff
    int d = 4;
}

void parent_func_clone() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
    
    // extra parent stuff
    int d = 4;
}

void independent_child() {
    int a = 1;
    int b = 2;
    int c = a + b;
    printf("%d", c);
}
