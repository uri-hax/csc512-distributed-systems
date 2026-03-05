#include <iostream>
#include <fstream>
#include <sstream>
#include <string>

// Function to count lines, words, and bytes in a file or input stream
void count_file(std::istream& input, const std::string& filename, int& total_lines, int& total_words, int& total_bytes) {
    std::string line;
    int line_count = 0, word_count = 0, byte_count = 0;
    
    while (std::getline(input, line)) {  // Read each line from input
        line_count++;
        byte_count += line.size() + 1;  // +1 accounts for newline character
        std::istringstream word_stream(line);
        std::string word;
        while (word_stream >> word) word_count++;  // Count words in the line
    }
    // Update the total counts
    total_lines += line_count;
    total_words += word_count;
    total_bytes += byte_count;

    // Print results for the current file
    std::cout << line_count << " " << word_count << " " << byte_count << " " << filename << std::endl;
}

int main(int argc, char* argv[]) {
    int total_lines = 0, total_words = 0, total_bytes = 0;
    
    if (argc == 1) {
        // If no arguments, read from standard input
        count_file(std::cin, "(stdin)", total_lines, total_words, total_bytes);
    } else {
        int file_count = 0;
        for (int i = 1; i < argc; ++i) {
            std::ifstream file(argv[i]);  // Try to open the file
            if (!file) {
                // Print error message when the file cannot be opened
                std::cerr << argv[0] << ": " << argv[i] << ": No such file or directory" << std::endl;
                continue;  // Skip this file and continue with others
            }
            count_file(file, argv[i], total_lines, total_words, total_bytes);
            file_count++;
        }
        
        // Print total counts only if there were valid files processed
        if (file_count > 0) {
            std::cout << total_lines << " " << total_words << " " << total_bytes << " total" << std::endl;
        } else {
            // If no valid files, still print "total" but with counts as 0
            std::cout << "0 0 0 total" << std::endl;
        }
    }
    return 0;  // Successful execution
}
