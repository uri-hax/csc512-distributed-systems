#ifndef H_VECTOR
#define H_VECTOR

#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <assert.h>

typedef char* vector_elem_t;

typedef struct vector {
	vector_elem_t* data;
	size_t size;
	size_t capacity;
} vector_t;

bool vector_ok(vector_t* vec) {
	return (
		(vec != NULL)
		&& (vec->data != NULL)
		&& (vec->size >= 0)
		&& (vec->capacity > 0)
		&& (vec->size <= vec->capacity)
	);
}

vector_t vector_new(size_t capacity) {
	assert(capacity > 0);
	vector_t vec;
	vec.data = (vector_elem_t*)malloc(capacity * sizeof(vector_elem_t));
	vec.capacity = capacity;
	vec.size = 0;
	assert(vector_ok(&vec));
	return vec;
}

void vector_delete(vector_t* vec) {
	assert(vector_ok(vec));
	free(vec->data);
	vec->data = NULL;
	vec->size = 0;
	vec->capacity = 0;
	assert(!vector_ok(vec));
}

void vector_resize(vector_t* vec) {
	assert(vector_ok(vec));
	size_t new_capacity = 2 * vec->capacity + 1;
	vector_elem_t* new_data = (vector_elem_t*)malloc(new_capacity * sizeof(vector_elem_t));
	memcpy(new_data, vec->data, vec->size * sizeof(vector_elem_t));
	free(vec->data);
	vec->data = new_data;
	vec->capacity = new_capacity;
	assert(vector_ok(vec));
}

void vector_push_back(vector_t* vec, vector_elem_t elem) {
	assert(vector_ok(vec));
	if (vec->size == vec->capacity)
		vector_resize(vec);
	vec->data[vec->size] = elem;
	vec->size += 1;
	assert(vector_ok(vec));
}

void vector_pop_back(vector_t* vec) {
	assert(vector_ok(vec));
	assert(vec->size > 0);
	vec->size -= 1;
	assert(vector_ok(vec));
}

#endif