#!/usr/bin/env bash

# Build phase - compile everything
bash build.sh

# If this is just the build phase (no args)
if [ $# -eq 0 ]; then
    exit $?
fi

# Run phase - execute the programs
# Don't capture in variable, just pipe directly to stdout
./readfile | ./linebreaker

# Also save to file
./readfile | ./linebreaker > output.text