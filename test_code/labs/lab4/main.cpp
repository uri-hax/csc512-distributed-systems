
#include <iostream>
#include <random>
#include <vector>
#include <thread>
#include <fstream>
#include <sys/stat.h>
#include <string>

std::string directoryName = "logFolder";

void threadFunc(int num) {
    // Calculate the factorial of num
    unsigned long long factorial = 1;
    for (int i = 1; i <= num; ++i) {
        factorial *= i;
    }

    // Create a file with the proper permissions
    std::string fileName = directoryName + "/thread" + std::to_string(num) + ".txt";
    std::ofstream outFile(fileName);
    if (!outFile) {
        std::cerr << "Error opening file: " << fileName << std::endl;
        return;
    }

    // Write the information to the file
    outFile << "This thread's value is " << num << ".\n";
    outFile << "The factorial of " << num << " is " << factorial << ".\n";

    // Close the file
    outFile.close();

    // Set file permissions to 0755
    chmod(fileName.c_str(), 0755);
}

int genRandNumber(int min, int max) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> distrib(min, max);
    return distrib(gen);
}

int main(int argc, char**) {
    // Generate random number using genRandNumber
    int randomNum = genRandNumber(1, 10);

    // Check for arguments
    if (argc > 1) {
        std::cout << "You silly rabbit, this program accepts no arguments; running with 3 threads." << std::endl;
        randomNum = 3;
    }

    // Create the directory with 0755 permissions
    mkdir(directoryName.c_str(), 0755);

    // Create the proper amount of threads
    std::vector<std::thread> threadList;
    for (int i = 1; i <= randomNum; i++) {
        threadList.emplace_back(threadFunc, i);
    }

    // Wait for all threads to complete
    for (auto& thread : threadList) {
        thread.join();
    }

    return 0;
}
