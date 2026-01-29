#! /usr/bin/env bash

### compile all c code in the current directory
for filename in *".c"
do
  if [ $filename == "*.c" ]; then
    current_dir=$(pwd)
    echo -e "Oops, we found no C code in the directory: $current_dir"  >&2
  else
    ### strip .c from file names
    output="${filename//.c}"
    if [ $output == "sentence" ]; then
      gcc -o $output $filename ../fio/fio.c
    elif [ $output == "mismatch" ]; then
      gcc -o $output $filename ../fio/fio.c
    else
      gcc -o $output $filename
    fi
  fi
done
