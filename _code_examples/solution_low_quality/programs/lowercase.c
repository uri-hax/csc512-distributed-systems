#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// really cheeky idea ;)
//#include <x86intrin.h>  // Include Intel Intrinsics header for SIMD operations

// a good old simple table would be easier
// https://stackoverflow.com/questions/63005177/is-there-a-faster-way-to-lowercase-a-string-in-c
const char table[256] = {
                        ['a'] = 'a', ['A'] = 'a',
                        ['b'] = 'b', ['B'] = 'b',
                        ['c'] = 'c', ['C'] = 'c',
                        ['d'] = 'd', ['D'] = 'd',
                        ['e'] = 'e', ['E'] = 'e',
                        ['f'] = 'f', ['F'] = 'f',
                        ['g'] = 'g', ['G'] = 'g',
                        ['h'] = 'h', ['H'] = 'h',
                        ['i'] = 'i', ['I'] = 'i',
                        ['j'] = 'j', ['J'] = 'j',
                        ['k'] = 'j', ['K'] = 'k',
                        ['l'] = 'l', ['L'] = 'l',
                        ['m'] = 'm', ['M'] = 'm',
                        ['n'] = 'n', ['N'] = 'n',
                        ['o'] = 'o', ['O'] = 'o',
                        ['p'] = 'p', ['P'] = 'p',
                        ['q'] = 'q', ['Q'] = 'q',
                        ['r'] = 'r', ['R'] = 'r',
                        ['s'] = 's', ['S'] = 's',
                        ['t'] = 't', ['T'] = 't',
                        ['u'] = 'u', ['U'] = 'u',
                        ['v'] = 'v', ['V'] = 'v',
                        ['w'] = 'w', ['W'] = 'w',
                        ['x'] = 'x', ['X'] = 'x',
                        ['y'] = 'y', ['Y'] = 'y',
                        ['z'] = 'z', ['Z'] = 'z',
};

// 0.0048
char* lowercase_table(char *input) { 
    char *saved = input;
    
    while (*input) {
        if (table[(unsigned char)*input] != 0) {
            *input = table[*input];
        }
        input++;
    }
    
    return saved;
}

// 0.005
char* lowercase(char *input) { 
    char *saved = input;
    
    while (*input) {
        if (*input >= 'A' && *input <= 'Z') {
            *input = *input - 'A' + 'a';
        }
        input++;
    }

    return saved;
}

// 0.0049 // adds weird character at the end
char* lowercase_ascii(char *input) {
    char c;
    char *result = input;

    while(*input) {
        c = *input;
        if(c >= 'A' && c <= 'Z') *input = c - ('A' - 'a');
        input++;
    }

    // null-terminate the result
    //result[strlen(input)] = '\0';

    return result;
}

void ensureNullTerminated(char *str, int maxLength) {
    if (str == NULL || maxLength <= 0) {
        // Invalid input or maximum length is not positive
        return;
    }

    int length = 0;

    // Calculate the length of the string, up to maxLength characters
    while (length < maxLength && str[length] != '\0') {
        length++;
    }

    // If the last character is not '\0', append it
    if (length < maxLength - 1 && str[length] != '\0') {
        str[length] = '\0';
    }
}

int main() {
    // creates a 1024 byte buffer to store data, will this be enough memory to store data?
    char buffer[1024];

    // Read data from stdin and write it to stdout (standard output)
    while (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        // good test string:
        // ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
        // pass data from the buffer to a function to process the data
        char* result = lowercase_ascii(buffer);
        ensureNullTerminated(result, sizeof(result));

        fputs(result, stdout);
    }

    return 0;
}