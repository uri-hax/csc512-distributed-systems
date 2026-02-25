#! /usr/bin/env bash

### compile all .c files in the current directory
mydir=$(pwd)
found=false

fio_loc="../fio/fio.c"

if [ -z "$fio_loc" ]; then
    exit 1
fi

# Loop through all .c files
for file in *.c; do
    if [ -e "$file" ]; then
        if [ $? -ne 0 ]; then
            exit 1
        fi
    gcc -Wall -Werror -o "${file%.c}" "$file" "$fio_loc"
    found=true
    fi
done

# Check if no .c files were found
if [ "$found" = false ]; then
    echo "Oops, we found no C code in the directory: $mydir"
    exit 1
fi