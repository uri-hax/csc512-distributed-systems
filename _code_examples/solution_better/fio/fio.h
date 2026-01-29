#ifndef FIO_H
#define FIO_H

#include <stdio.h>

FILE* fio_open(const char* const fname);
FILE* fio_create(const char* const fname);
void fio_write(FILE* file, const char* const data, const size_t bytes);

#endif