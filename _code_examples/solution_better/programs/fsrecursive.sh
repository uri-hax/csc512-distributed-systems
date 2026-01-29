#!/bin/bash
./fsrecursion | ./lowercase.sh | ./unique.sh | ./mismatch.sh > fsrecursion_unique_output.text
