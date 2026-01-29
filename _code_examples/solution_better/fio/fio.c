#include <stdio.h>
#include <assert.h>
#include "fio.h"

FILE* fio_open(const char* const fname) {
    FILE* file = fopen(fname, "r");
    assert(file != NULL);
    return file;
}

FILE* fio_create(const char* const fname) {
    FILE* file = fopen(fname, "a");
    assert(file != NULL);
    return file; 
}

void fio_write(FILE* file, const char* const data, const size_t bytes) {
    fwrite(data, 1, bytes, file);
}