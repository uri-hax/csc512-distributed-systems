#include <iostream>   
#include <random>     
#include <vector>   
#include <thread>       // For using std::thread
#include <fstream>    
#include <sys/stat.h>   // For mkdir() and chmod()
#include <string>   
#include <unistd.h>     // For access() and POSIX stuff

// Directory where all log files go
std::string directoryName = "logFolder";

/**
 * Computes the factorial of a given number.
 *    Ex: factorial(5) = 5 * 4 * 3 * 2 * 1 = 120
 *    Uses a simple loop, no recursion nonsense.
 */
unsigned long long factorial(int num) {
    unsigned long long result = 1;
    for (int i = 2; i <= num; i++) {
        result *= i;
    }
    return result;
}

/**
 * Each thread runs this function.
 *    - Computes the factorial of its assigned number.
 *    - Writes that info into a log file.
 *    - Sets file permissions to 0755.
 */
// Step 5: Create log file
void threadFunc(int num) {
    std::string fileName = directoryName + "/thread" + std::to_string(num) + ".txt";

    std::ofstream outFile(fileName);
    if (!outFile) {
        std::cerr << "Error creating file: " << fileName << std::endl;
        return;
    }

    // Write factorial computation
    unsigned long long fact = factorial(num);
    outFile << "This thread's value is " << num << ".\n";
    outFile << "The factorial of " << num << " is " << fact << ".\n";
    outFile.close(); // Done writing

    // Explicitly set file permissions to 0755
    chmod(fileName.c_str(), 0755);
}


/**
 * Generates a random number between `min` and `max` (inclusive).
 *    Uses a **non-deterministic** random generator.
 */
int genRandNumber(int min, int max) {
    std::random_device rd;  // Get a truly random seed from hardware
    std::mt19937 gen(rd()); // Seed the Mersenne Twister RNG
    std::uniform_int_distribution<> distrib(min, max); // Set range
    return distrib(gen); // Return random number
}

/**
 * Main function
 *    - Handles command-line arguments (rejects them).
 *    - Creates logFolder if it doesn't exist.
 *    - Generates threads based on a random number.
 *    - Ensures threads run and join properly.
 */
int main(int argc, char** argv) {
    // Step 1: Declare randomNum and handle arguments (This program takes NO args)
    int randomNum;
    if (argc > 1) {
        std::cout << "You silly rabbit, this program accepts no arguments; running with 3 threads.\n";
        randomNum = 3;
    } else {
        randomNum = genRandNumber(1, 10);
    }    

    // Step 3: Create logFolder directory (if it doesn't exist) with 0755 permissions
    mkdir(directoryName.c_str(), 0755);
    chmod(directoryName.c_str(), 0755); // Add this line to explicitly set correct permissions

    // Step 4: Create and launch threads
    std::vector<std::thread> threadList;
    for (int i = 1; i <= randomNum; i++) {
        threadList.emplace_back(threadFunc, i); // Launch thread
    }

    // Step 5: Wait for all threads to finish (thread.join() is REQUIRED)
    for (auto &t : threadList) {
        t.join(); // Ensure thread finishes before moving on
    }

    return 0;
}