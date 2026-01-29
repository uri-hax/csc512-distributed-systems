#! /usr/bin/env bash

buffer=$(cat -)
echo $buffer | tr " " "\n"
