#! /usr/bin/env bash

./build.sh

### unix demo: watch 5:00 to 10:55
# https://www.youtube.com/watch?v=tc4ROCJYbm0&t=297s&ab_channel=AT%26TTechChannel

### recreate unix demo from video
./sentence | ./makewords | ./lowercase | ./sort | ./unique | ./mismatch > unix_c_output.text

### update unix_dict_new_words.text with 
./sentence.sh | ./makewords.sh | ./lowercase.sh | ./sort.sh | ./unique.sh | ./mismatch.sh > unix_bash_output.text
