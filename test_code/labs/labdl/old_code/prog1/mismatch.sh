#!/usr/bin/env bash

# This script reads words from stdin and checks if they exist in unix_dict.text
# It prints only the words that are missing from the dictionary.

# -F (Fixed string matching) ensures exact word comparisons
# -x (Match whole line) ensures partial words are not matched
# -v (Invert match) prints only words NOT found in the dictionary
grep -Fxv -f unix_dict.text
