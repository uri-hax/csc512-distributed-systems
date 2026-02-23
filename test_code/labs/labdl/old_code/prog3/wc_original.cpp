#include <iostream>
#include <fstream>
#include <string>

void process_in(std::istream &input, const std::string &filename, 
    int &total_line_count, int &total_word_count, int &total_byte_count) {
    int line_count = 0;
    int word_count = 0;
    int byte_count = 0;

    std::string line;
    while (std::getline(input, line)) {
        line_count++;
        total_line_count++;
        byte_count += line.size() + 1; // +1 for newline character
        total_byte_count += line.size() + 1;

        bool in_word = false;
        for (char c : line) {
            if (std::isspace(c)) {
                if (in_word) {
                    word_count++;
                    total_word_count++;
                    in_word = false;
                }
            } else {
                in_word = true;
            }
        }
        if (in_word) {
            word_count++;
            total_word_count++;
        }
    }

    if (!filename.empty()) {
        std::cout << line_count << " " << word_count << " " << byte_count << " " << filename << std::endl;
    } else {
        std::cout << line_count << " " << word_count << " " << byte_count << " (stdin)" << std::endl;
    }
}

int main(int argc, char *argv[]) {
    int total_line_count = 0;
    int total_word_count = 0;
    int total_byte_count = 0;

    if (argc == 1) {
        process_in(std::cin, "", total_line_count, total_word_count, total_byte_count);
    } else {
        for (int i = 1; i < argc; i++) {
            std::ifstream file(argv[i]);
            if (!file) {
                std::cerr << (argc > 0 ? argv[0] : "wc") << ": " << argv[i] << ": No such file or directory" << std::endl;
                continue;
            }
            process_in(file, argv[i], total_line_count, total_word_count, total_byte_count);
        }
    }

    // Print totals if multiple files are processed
    if (argc > 2) {
        std::cout << total_line_count << " " << total_word_count << " " << total_byte_count << " total" << std::endl;
    }

    return 0;
}