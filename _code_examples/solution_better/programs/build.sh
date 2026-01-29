#!/bin/bash
./clean.sh

C=c
gcc -O2 -Wall sentence.$C ../fio/fio.$C -o sentence 
gcc -O2 -Wall makewords.$C -o makewords
gcc -O2 -Wall lowercase.$C -o lowercase
gcc -O2 -Wall sort.$C -o sort
gcc -O2 -Wall unique.$C -o unique
gcc -O2 -Wall mismatch.$C ../fio/fio.$C -o mismatch 
gcc -O2 -Wall fsrecursive.$C ../fio/fio.$C -o fsrecursion
