#! /usr/bin/env bash

# read words from stdin, sort them, and print the sorted words
# sort

# insertion sort for arrays
insertion_sort() {
    local arr=("$@")  # copy input array
    local len=${#arr[@]}

    for ((i = 1; i < len; i++)); do
        key="${arr[i]}"
        j=$((i - 1))

        # move elements of arr[0..i-1] that are greater than key
        # to one position ahead of their current position
        while [[ $j -ge 0 && "${arr[j]}" > "$key" ]]; do
            arr[j + 1]="${arr[j]}"
            ((j--))
        done

        arr[j + 1]="$key"
    done

    # let's see the final hopefully sorted array
    for ((i = 0; i < len; i++)); do
        echo "${arr[i]}"
    done
}


# empty array to store words
words=()

# read input line by line
while read -r line; do
    # 'read' splits each line into words
    read -ra line_words <<< "$line"
    
    # append the words to the 'words' array
    for word in "${line_words[@]}"; do
        words+=("$word")
    done
done

insertion_sort "${words[@]}"