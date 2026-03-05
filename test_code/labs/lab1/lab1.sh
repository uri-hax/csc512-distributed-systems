#! /usr/bin/env bash

if [ $# -eq 0 ]; then
    gcc -Wall lab1.c -o lab1
    exit $?
fi

# get filename to compile from command line (how do you read just the firsy argument?)
filename=$1

# compile lab1.c to lab1 (you did something similar in Lab 0)
gcc -Wall "$filename" -o lab1

# get the arguments passed when running lab1.sh (*this is the hard part)
args=${@:2}

# run the lab1 program with those arguments (*this is the other hard part)
./lab1 $args
