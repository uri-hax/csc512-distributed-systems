#include <stdio.h>
#include <string.h>
#include "lib/vector.h"

int qsort_strcmp(const void* s1, const void* s2) {
	return strcmp(*(const char**)s1, *(const char**)s2);
}

int main(const int argc, const char* const argv[]) {
	// Store each line on stdin into a vector.
	vector_t vec = vector_new(64);
	size_t bytes = 0;
	char* buf = NULL;
	while (getline(&buf, &bytes, stdin) > 0) {
		vector_push_back(&vec, buf);
		buf = NULL;
	}
	if (vec.size == 0) 
		return 0;

	// If the last line does not contain a newline, add one.
	char* last = vec.data[vec.size - 1];
	size_t last_size = strlen(last);
	if ((last_size == 0) || (last[last_size - 1] != '\n')) {
		char* new_last = malloc(last_size + 2);
		memcpy(new_last, last, last_size);
		new_last[last_size] = '\n';
		new_last[last_size + 1] = '\0';
		vec.data[vec.size - 1] = new_last;
		free(last);
	}

	// Sort and print the lines.
	qsort(vec.data, vec.size, sizeof(vector_elem_t), qsort_strcmp);
	for (int i = 0; i < vec.size; ++i)
		printf("%s", vec.data[i]);
	return 0;
}
