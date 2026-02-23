#! /usr/bin/env bash

# Define the filename to be read
filename="unix_sentence.text"

# Check if the file exists before attempting to read it
if [[ ! -f "$filename" ]]; then
    # Print an error message to stderr if the file does not exist
    echo "Error: Could not open file $filename" >&2
    exit 1  # Exit with a non-zero status to indicate failure
fi

# Read and output the contents of the file to stdout using `tee`
# `tee` will take input from the file and print it to the console
# This allows the script to function correctly in a pipeline
tee < "$filename"
