#!/bin/bash

# Read stdin into an array.
readarray arr

# Selection sort the array.
size="${#arr[@]}"
for ((i = 0; i < size; i++))
do
    # Select the minimum element.
    mj=$i
    for ((j = i; j < size; j++))
    do
        if [[ ${arr[j]} < ${arr[mj]} ]]; then
            mj=$j;
        fi
    done
    
    # Swap and print.
    tmp=${arr[i]}
    arr[$i]=${arr[mj]}
    arr[$mj]=$tmp
    echo ${arr[i]}
done