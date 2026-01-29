#include <dirent.h>
#include <stdio.h>
#include <string.h>
#include "lib/vector.h"
#include "../fio/fio.h"

char* path_concat(char* path, char* sub_path) {
    const size_t path_size = strlen(path);
    const size_t sub_path_size = strlen(sub_path);
    char* new_path = malloc(path_size + sub_path_size + 2);
    memcpy(new_path, path, path_size);
    new_path[path_size] = '/';
    memcpy(new_path + path_size + 1, sub_path, sub_path_size + 1);
    return new_path;
}

char* path_basename(char* path) {
    char* basename = path;
    while (path[0] != '\0') {
        if (path[0] == '/') 
            basename = path + 1;
        path += 1;
    }
    return basename;
}

int main(const int argc, const char* const argv[]) {
    // Create the output file.
    FILE* out_file = fio_create("fsrecursion_output.text");
    
    // Get the root path from the file.
    char* root_path = NULL;
    size_t root_path_size = 0;
    FILE* root_path_file = fio_open("fsrecursion_start.text");
    getline(&root_path, &root_path_size, root_path_file);

    // Add root path to the stack.
    vector_t vec = vector_new(64);
    vector_push_back(&vec, root_path);
    
    // Depth-first search of the file system.
    while (vec.size > 0) {
        // Get the next path from the stack.
        char* path = vec.data[vec.size - 1];
        vector_pop_back(&vec);

        // Check if the path is a directory.
        DIR* dir = opendir(path);
        if (dir == NULL) {
            free(path);
            continue;
        }

        // Output the current directory.
        if (strcmp(path, "/") != 0) {
            char* basename = path_basename(path);
            printf("%s\n", basename);
            fio_write(out_file, basename, strlen(basename));
        }

        // Add any subdirectories to the stack.
        struct dirent* ent = NULL;
        while ((ent = readdir(dir)) != NULL)
            // Ignore any symbolic links.
            if (strcmp(ent->d_name, ".") != 0 && strcmp(ent->d_name, "..") != 0)
                vector_push_back(&vec, path_concat(path, ent->d_name));

        // Clean up.
        assert(closedir(dir) == 0);
        free(path);
    }
}