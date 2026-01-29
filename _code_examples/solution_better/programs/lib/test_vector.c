#include <string.h>
#include "vector.h"

void test_vector() {
    vector_t vec = vector_new(1);
    assert(vec.capacity == 1);
    assert(vec.size == 0);

    vector_push_back(&vec, "hello");
    assert(vec.capacity == 1);
    assert(vec.size == 1);
    assert(strcmp(vec.data[0], "hello") == 0);

    vector_push_back(&vec, "world");
    assert(vec.capacity >= 2);
    assert(vec.size == 2);
    assert(strcmp(vec.data[0], "hello") == 0);
    assert(strcmp(vec.data[1], "world") == 0);

    vector_delete(&vec);
}

int main(const int argc, const char* const argv[]) {
    test_vector();
}