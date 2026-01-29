#!/bin/bash

while read -r line; do 
    if ! [ "$(grep -R $line "unix_dict.text")" ]; then
        echo $line
    fi
done