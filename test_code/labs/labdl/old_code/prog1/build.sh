#!/usr/bin/env bash

# Get the current working directory
current_dir=$(pwd)

# Move to the programs directory (ensuring we run from the correct place)
cd "$(dirname "$0")"

# Find all .c files in the directory
c_files=(*.c)

# Check if there are no C files
if [ ${#c_files[@]} -eq 0 ]; then
    echo "Oops, we found no C code in the directory: $current_dir/programs" >&2
    exit 1
fi

# Compile each .c file into an executable
for file in "${c_files[@]}"; do
    executable="${file%.c}"  # Remove .c extension for the output file
    gcc -Wall -Werror -I ../fio -o "$executable" "$file" ../fio/fio.c  # Include fio directory

    # Check if compilation was successful
    if [ $? -eq 0 ]; then
        echo "Compiled $file -> $executable"
    else
        echo "Error: Compilation failed for $file" >&2
        exit 1
    fi
done

echo "All C programs compiled successfully!"
