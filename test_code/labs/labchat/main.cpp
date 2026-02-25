#include <iostream>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <vector>
#include <chrono>

struct Process {
    int id;                 // Unique process identifier
    int arrival_time;       // Time when the process arrives in the queue
    int burst_time;         // Total CPU time required by the process
    int remaining_time;     // Remaining CPU time (used for RR)
    int completion_time;    // Time when the process completes execution
    int turnaround_time;    // Turnaround time (completion_time - arrival_time)
    int waiting_time;       // Waiting time (turnaround_time - burst_time)

    // Constructor for easy initialization
    Process(int pid, int arrival, int burst)
        : id(pid), arrival_time(arrival), burst_time(burst),
          remaining_time(burst), completion_time(0),
          turnaround_time(0), waiting_time(0) {}

    // Default constructor
    Process() : id(0), arrival_time(0), burst_time(0), remaining_time(0),
                completion_time(0), turnaround_time(0), waiting_time(0) {}
};

// Comparison for FCFS scheduling (prioritizes earlier arrivals)
struct CompareFCFS {
    bool operator()(const Process& p1, const Process& p2) {
        return p1.arrival_time > p2.arrival_time; // Min-heap behavior
    }
};

// ===== Shared Data Structures =====
std::priority_queue<Process, std::vector<Process>, CompareFCFS> fcfs_queue;  // For FCFS
std::queue<Process> rr_queue;  // For Round Robin (no priority needed)

// ===== Synchronization Primitives =====
std::mutex mtx;  // Protects shared queues and variables
std::condition_variable cv;  // Used to notify threads of new processes

// ===== Scheduling Control Variables =====
bool all_processes_submitted = false;  // Indicates no more processes will arrive
int current_time = 0;  // Simulated CPU clock (for tracking arrivals/completions)
int time_quantum = 2;   // Time slice for Round Robin (adjustable)

// ===== Metrics Tracking =====
std::vector<Process> completed_processes;  // Stores finished processes for stats

void executeProcess(int pid) {
    // Lock the mutex to protect shared resources
    std::unique_lock<std::mutex> lock(mtx);

    // Find the process in either queue (FCFS or RR)
    Process current_process;
    bool process_found = false;

    // Check FCFS queue
    if (!fcfs_queue.empty()) {
        current_process = fcfs_queue.top();
        if (current_process.id == pid) {
            fcfs_queue.pop();
            process_found = true;
        }
    }

    // If not in FCFS, check RR queue
    if (!process_found && !rr_queue.empty()) {
        // Need to search through RR queue (linear search since it's a regular queue)
        std::queue<Process> temp_queue;
        while (!rr_queue.empty()) {
            Process p = rr_queue.front();
            rr_queue.pop();
            if (p.id == pid) {
                current_process = p;
                process_found = true;
                break;
            }
            temp_queue.push(p);
        }
        // Restore the queue
        while (!temp_queue.empty()) {
            rr_queue.push(temp_queue.front());
            temp_queue.pop();
        }
    }

    if (!process_found) {
        std::cerr << "Process " << pid << " not found in any queue!\n";
        return;
    }

    // Calculate the actual execution time (minimum of remaining time and quantum)
    int execution_time = (current_process.remaining_time < time_quantum) ? 
                         current_process.remaining_time : time_quantum;

    // Release the lock during execution (no need to hold it while sleeping)
    lock.unlock();

    // Simulate process execution (critical work)
    std::cout << "Process " << pid << " executing for " << execution_time << " units\n";
    std::this_thread::sleep_for(std::chrono::milliseconds(execution_time));

    // Reacquire the lock to update process state
    lock.lock();

    // Update process state
    current_process.remaining_time -= execution_time;
    current_time += execution_time;

    // Check if process completed
    if (current_process.remaining_time <= 0) {
        current_process.completion_time = current_time;
        current_process.turnaround_time = current_process.completion_time - current_process.arrival_time;
        current_process.waiting_time = current_process.turnaround_time - current_process.burst_time;
        completed_processes.push_back(current_process);
        std::cout << "Process " << pid << " completed at time " << current_time << "\n";
    } else {
        // Re-add to RR queue if not completed
        rr_queue.push(current_process);
        std::cout << "Process " << pid << " requeued with remaining time " 
                  << current_process.remaining_time << "\n";
    }

    // Notify other threads
    cv.notify_one();
}

// FCFS Scheduling Algorithm
void firstComeFirstServed() {
    while (true) {
        std::unique_lock<std::mutex> lock(mtx);
        
        // Wait until there's work or all processes are submitted
        cv.wait(lock, [] {
            return !fcfs_queue.empty() || all_processes_submitted;
        });

        // Exit condition: no more work and all processes submitted
        if (fcfs_queue.empty() && all_processes_submitted) {
            break;
        }

        if (!fcfs_queue.empty()) {
            // Get the next process (earliest arrival)
            Process current = fcfs_queue.top();
            fcfs_queue.pop();
            lock.unlock();  // Release lock during execution

            // Execute the entire burst time (FCFS doesn't preempt)
            std::cout << "FCFS executing Process " << current.id 
                      << " for " << current.burst_time << " units\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(current.burst_time));

            // Update completion metrics
            lock.lock();
            current.completion_time = current_time + current.burst_time;
            current.turnaround_time = current.completion_time - current.arrival_time;
            current.waiting_time = current.turnaround_time - current.burst_time;
            completed_processes.push_back(current);
            current_time = current.completion_time;
            std::cout << "FCFS completed Process " << current.id 
                      << " at time " << current_time << "\n";
        }
    }
    std::cout << "FCFS scheduler exiting\n";
}

// Round Robin Scheduling Algorithm
void roundRobin() {
    while (true) {
        std::unique_lock<std::mutex> lock(mtx);
        
        // Wait until there's work or all processes are submitted
        cv.wait(lock, [] {
            return !rr_queue.empty() || all_processes_submitted;
        });

        // Exit condition: no more work and all processes submitted
        if (rr_queue.empty() && all_processes_submitted) {
            break;
        }

        if (!rr_queue.empty()) {
            // Get the next process
            Process current = rr_queue.front();
            rr_queue.pop();
            lock.unlock();  // Release lock during execution

            // Determine execution time (minimum of quantum or remaining time)
            int execution_time = std::min(time_quantum, current.remaining_time);
            std::cout << "RR executing Process " << current.id 
                      << " for " << execution_time << " units\n";
            std::this_thread::sleep_for(std::chrono::milliseconds(execution_time));

            // Update process state
            lock.lock();
            current.remaining_time -= execution_time;
            current_time += execution_time;

            if (current.remaining_time <= 0) {
                // Process completed
                current.completion_time = current_time;
                current.turnaround_time = current.completion_time - current.arrival_time;
                current.waiting_time = current.turnaround_time - current.burst_time;
                completed_processes.push_back(current);
                std::cout << "RR completed Process " << current.id 
                          << " at time " << current_time << "\n";
            } else {
                // Requeue the process
                rr_queue.push(current);
                std::cout << "RR requeued Process " << current.id 
                          << " (remaining: " << current.remaining_time << ")\n";
            }
        }
    }
    std::cout << "RR scheduler exiting\n";
}

#include <fstream>
#include <sstream>

int main(int argc, char* argv[]) {
    // Parse command line arguments
    bool use_file = false;
    std::string filename;
    int quantum = 2; // Default time quantum

    if (argc > 1) {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "-f" && i + 1 < argc) {
                use_file = true;
                filename = argv[++i];
            } else if (arg == "-q" && i + 1 < argc) {
                quantum = std::stoi(argv[++i]);
            } else if (arg == "-h") {
                std::cout << "Usage: " << argv[0] << " [-f filename] [-q quantum]\n";
                std::cout << "Options:\n";
                std::cout << "  -f <filename>  Read processes from file\n";
                std::cout << "  -q <quantum>   Set time quantum for RR (default: 2)\n";
                return 0;
            }
        }
    }

    // Set time quantum
    time_quantum = quantum;

    // Read processes from file or stdin
    std::vector<Process> processes;
    if (use_file) {
        std::ifstream infile(filename);
        if (!infile) {
            std::cerr << "Error: Could not open file " << filename << "\n";
            return 1;
        }

        std::string line;
        while (std::getline(infile, line)) {
            std::istringstream iss(line);
            int id, arrival, burst;
            if (!(iss >> id >> arrival >> burst)) {
                std::cerr << "Warning: Invalid line format: " << line << "\n";
                continue;
            }
            processes.emplace_back(id, arrival, burst);
        }
    } else {
        std::cout << "Enter processes (id arrival_time burst_time), one per line.\n";
        std::cout << "Enter 'done' when finished.\n";
        
        std::string line;
        while (std::getline(std::cin, line)) {
            if (line == "done") break;
            
            std::istringstream iss(line);
            int id, arrival, burst;
            if (!(iss >> id >> arrival >> burst)) {
                std::cerr << "Invalid input. Try again.\n";
                continue;
            }
            processes.emplace_back(id, arrival, burst);
        }
    }

    if (processes.empty()) {
        std::cerr << "Error: No processes to schedule\n";
        return 1;
    }

    // Producer thread to add processes
    std::thread producer([&processes]() {
        for (auto& p : processes) {
            std::this_thread::sleep_for(std::chrono::milliseconds(p.arrival_time));
            
            std::lock_guard<std::mutex> lock(mtx);
            fcfs_queue.push(p);
            rr_queue.push(p);
            cv.notify_all();
            std::cout << "Added Process " << p.id << " (arrival: " << p.arrival_time 
                      << ", burst: " << p.burst_time << ")\n";
        }

        std::lock_guard<std::mutex> lock(mtx);
        all_processes_submitted = true;
        cv.notify_all();
    });

    // Start scheduler threads
    std::cout << "\nStarting FCFS Scheduling:\n";
    std::thread fcfs_thread(firstComeFirstServed);
    
    // Wait for FCFS to complete
    fcfs_thread.join();
    
    // Reset for RR scheduling
    {
        std::lock_guard<std::mutex> lock(mtx);
        current_time = 0;
        completed_processes.clear();
        all_processes_submitted = false;
    }

    // Re-add processes for RR
    std::thread producer_rr([&processes]() {
        for (auto& p : processes) {
            std::this_thread::sleep_for(std::chrono::milliseconds(p.arrival_time));
            
            std::lock_guard<std::mutex> lock(mtx);
            rr_queue.push(p);
            cv.notify_all();
        }

        std::lock_guard<std::mutex> lock(mtx);
        all_processes_submitted = true;
        cv.notify_all();
    });

    std::cout << "\nStarting Round Robin Scheduling (quantum = " << quantum << "):\n";
    std::thread rr_thread(roundRobin);

    producer.join();
    producer_rr.join();
    rr_thread.join();

    // Print statistics
    std::cout << "\nScheduling Statistics:\n";
    std::cout << "Process ID | Turnaround Time | Waiting Time\n";
    for (const auto& p : completed_processes) {
        std::cout << "    " << p.id << "     |       " << p.turnaround_time
                  << "       |      " << p.waiting_time << "\n";
    }

    return 0;
}