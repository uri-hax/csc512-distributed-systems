#! /usr/bin/env bash

### unix demo: watch 5:00 to 10:55
# https://www.youtube.com/watch?v=tc4ROCJYbm0&t=297s&ab_channel=AT%26TTechChannel

### recreate unix demo from video


### update unix_dict_new_words.text with 

# Move to the correct directory (programs/)
cd "$(dirname "$0")"

# Compile all C programs first
./build.sh

# Run the 1982 UNIX demo pipeline with C programs
./sentence | ./makewords | ./lowercase | ./sort | ./unique | ./mismatch > unix_c_output.text

# Run the 1982 UNIX demo pipeline with Bash scripts
./sentence.sh | ./makewords.sh | ./lowercase.sh | ./sort.sh | ./unique.sh | ./mismatch.sh > unix_bash_output.text

# Notify the user that the process is complete
echo "UNIX Demo completed! Check unix_c_output.text and unix_bash_output.text for results."
