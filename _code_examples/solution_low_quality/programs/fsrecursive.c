#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>

#define MAX_PATH_LEN 4096

void listFolders(const char *path, char ***folderList, size_t *listSize) {
    DIR *dir;
    struct dirent *entry;
    struct stat statbuf;

    if ((dir = opendir(path)) == NULL) {
        perror("opendir");
        return;
    }

    char newFolder[MAX_PATH_LEN];
    while ((entry = readdir(dir)) != NULL) {
        snprintf(newFolder, sizeof(newFolder), "%s/%s", path, entry->d_name);

        if (stat(newFolder, &statbuf) == -1) {
            perror("stat");
            continue;
        }

        if (S_ISDIR(statbuf.st_mode)) {
            if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
                continue;
            }

            // Resize the folderList array if needed
            if (*listSize % 100 == 0) {
                *folderList = (char **)realloc(*folderList, (*listSize + 100) * sizeof(char *));
                if (*folderList == NULL) {
                    perror("realloc");
                    exit(EXIT_FAILURE);
                }
            }

            (*folderList)[*listSize] = (char *)malloc(MAX_PATH_LEN);
            strcpy((*folderList)[*listSize], entry->d_name); // Store just the folder name
            (*listSize)++;

            listFolders(newFolder, folderList, listSize); // Pass the full path to the folder
        }
    }

    closedir(dir);
}

// hard coded a few files for easier testing
int main() {
    char **folderList = NULL; // initialize an empty array of strings to store folder names
    size_t listSize = 0;
    const char *startPath = "dir_test"; // you can change this to your desired starting directory 
                                    // dir_test is our test case

    listFolders(startPath, &folderList, &listSize);

    FILE *fptr;

    // open a file in writing mode
    fptr = fopen("fsrecursion_output.text", "w");

    // print each foldername from folderList
    for (size_t i = 0; i < listSize; i++) {
        printf("%s\n", folderList[i]);  // stdout
        fprintf(fptr,"%s\n", folderList[i]);     // write some text to the file
        free(folderList[i]);
    }

    // close the file
    fclose(fptr);

    // free the allocated memory
    free(folderList);

    return 0;
}