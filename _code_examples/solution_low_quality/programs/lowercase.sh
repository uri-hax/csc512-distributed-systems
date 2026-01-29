#! /usr/bin/env bash

buffer=$(cat -)

# output="${buffer,,}" # 0.0075 # does not consistently work

output=$(echo "$buffer" | tr '[:upper:]' '[:lower:]') # 0.0095
# tr is system utility designed for text translation

echo "$output"
