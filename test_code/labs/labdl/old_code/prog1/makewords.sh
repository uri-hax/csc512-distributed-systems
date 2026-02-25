#! /usr/bin/env bash

# Read input from stdin, convert spaces to newlines, and remove empty lines
tr ' ' '\n' | sed '/^$/d'
