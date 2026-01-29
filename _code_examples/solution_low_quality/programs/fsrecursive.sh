#! /usr/bin/env bash
./fsrecursive | ./unique.sh | ./mismatch.sh > fsrecursion_unique_output.text