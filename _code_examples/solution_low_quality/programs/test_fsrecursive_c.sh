#!/bin/bash

# clean the text file in case student's changed it
echo -n "dir_test" > fsrecursion_start.text

# Use an if-else statement to check if the file exists.
if [ -f "fsrecursive" ]; then
    ./fsrecursive
else
    if [ -f "fsrecursion" ]; then
        ./fsrecursion
    else
        echo "We could not find the fsrecursive or fsrecursion programs."
    fi
fi

# clean the text file in case student's changed it
echo -n "/var" > fsrecursion_start.text
