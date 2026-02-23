#include <stdio.h>     
#include <stdlib.h>     
#include <string.h>     
#include <dirent.h>     // Directory handling functions
#include <sys/types.h>  // Data types for system calls
#include <sys/stat.h>   // File status functions
#include <unistd.h>     // UNIX standard functions

#define MAX_PATH 1024  // Maximum path length for directories
#define OUTPUT_FILE "fsrecursion_output.text"  // Output filename to store results

/**
 * Recursively traverses directories and writes folder names to a file.
 */
void traverseDirectory(const char *dirname, FILE *output_file) {
    DIR *dir = opendir(dirname);  // Attempt to open the specified directory
    if (!dir) {  
        fprintf(stderr, "Error: Cannot open directory %s\n", dirname);  
        return;  // If directory cannot be opened, return without processing
    }

    struct dirent *entry;
    
    // Read each entry inside the directory
    while ((entry = readdir(dir)) != NULL) {  
        // Check if the entry is a directory (folders only)
        if (entry->d_type == DT_DIR) {  
            // Skip special entries "." (current directory) and ".." (parent directory)
            if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
                continue;

            char path[MAX_PATH];  // Buffer to store full directory path
            snprintf(path, sizeof(path), "%s/%s", dirname, entry->d_name);  
            // Constructs the full directory path as "parent_directory/child_directory"

            fprintf(output_file, "%s\n", path);  // Write the folder name to the output file
            printf("%s\n", path);  // Also print the folder name to standard output

            traverseDirectory(path, output_file);  // Recursively call function for subdirectories
        }
    }

    closedir(dir);  // Close directory after processing all entries
}

int main() {
    char start_dir[MAX_PATH];  // Buffer to store the starting directory path

    // Open the input file containing the starting directory name
    FILE *input_file = fopen("fsrecursion_start.text", "r");
    if (!input_file) {  
        fprintf(stderr, "Error: Could not open fsrecursion_start.text\n");
        return 1;  // Exit with error if file cannot be opened
    }

    // Read the starting directory from the input file
    if (!fgets(start_dir, sizeof(start_dir), input_file)) {  
        fprintf(stderr, "Error: Could not read starting directory\n");
        fclose(input_file);  // Close file before exiting
        return 1;
    }
    fclose(input_file);  // Close input file as it's no longer needed

    // Remove any trailing newline character from the directory path
    start_dir[strcspn(start_dir, "\n")] = '\0';

    // Open the output file for writing results
    FILE *output_file = fopen(OUTPUT_FILE, "w");
    if (!output_file) {  
        fprintf(stderr, "Error: Could not open %s for writing\n", OUTPUT_FILE);
        return 1;  // Exit with error if file cannot be opened
    }

    // Start recursive directory traversal from the given starting directory
    traverseDirectory(start_dir, output_file);

    fclose(output_file);  // Close output file after writing all results
    return 0;  // Indicate successful execution
}
