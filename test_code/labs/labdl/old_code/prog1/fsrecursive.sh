#!/usr/bin/env bash

# Run fsrecursive to collect all folder names, convert to lowercase, remove duplicates,
# and filter out names found in unix_dict.text.
./fsrecursive | tr '[:upper:]' '[:lower:]' | sort | uniq | grep -Fxv -f unix_dict.text > fsrecursion_unique_output.text
