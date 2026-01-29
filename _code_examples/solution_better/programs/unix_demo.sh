#!/bin/bash
./build.sh
./sentence | ./makewords | ./lowercase | ./sort | ./unique | ./mismatch > unix_c_output.text
./sentence.sh | ./makewords.sh | ./lowercase.sh | ./sort.sh | ./unique.sh | ./mismatch.sh > unix_bash_output.text