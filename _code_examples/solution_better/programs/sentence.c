#include "../fio/fio.h"

int main(const int argc, const char* const argv[]) {
    // Not much to say here. Print all the lines.
    FILE* file = fio_open("unix_sentence.text");
    char buf[4096];
    while (fgets(buf, sizeof(buf) / sizeof(buf[0]), file) > 0)
        fputs(buf, stdout);
    return 0;
}