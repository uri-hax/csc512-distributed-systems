#! /usr/bin/env bash

# associative arrays are faster - not available in Bash v3
# declare -A unix_dict

# read input line by line
while read -r line; do 
   # use grep to check if line is in the unix_dict.text file
   if ! [ "$(grep -R $line "unix_dict.text")" ]; then
      echo $line
   fi
done
