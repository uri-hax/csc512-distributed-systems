#include <iostream>
#include <fstream>

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <input_file> <output_file>" << std::endl;
        return 1;
    }
    
    std::ifstream input_file(argv[1]);
    std::ofstream output_file(argv[2]);
    
    std::string line;
    while (std::getline(input_file, line)) {
        std::cout << line << std::endl; 
        output_file << line << std::endl;
    }
    
    input_file.close();
    output_file.close();
    
    return 0;
}