#include <stdio.h>

void function_a() {
    int x = 10;
    int y = 20;
    int z = x + y;
    printf("Result: %d
", z);
}

// This is a Type I clone of function_a
// It has different comments and whitespace
void function_b() {
    int x = 10; 
    int y = 20; 

    int z = x + y; 

    printf("Result: %d
", z);
}

int main() {
    function_a();
    function_b();
    return 0;
}
