#!/bin/bash

# # idea 1 using just sort
buffer=$(cat -)
words=$(echo "$buffer" | tr ' ' '\n')
unique_words=$(echo "$words" | sort -u)
echo "$unique_words"

# test case = a\nb
# echo " a \n a \n b" | ./unique.sh