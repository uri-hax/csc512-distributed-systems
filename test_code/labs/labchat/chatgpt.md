Deepseek chat log:

I want to write a program in cpp that simulates two different scheduling algorithms, FCFS (first come first served) and RR (round robin). Threads will represent processes, each performing dummy tasks to emulate execution cycles. The goal is to use these scheduling algorithms to manage the execution order of these threads effectively.
To begin, can you help me define a structure 'Process'  with attributes like process ID, arrival time, burst time, and for RR, additional attributes like remaining burst time may be necessary.

Stencil code:
#include <iostream>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <vector>
#include <chrono>

// TODO: Define a 'Process' structure with necessary attributes
struct Process {
    // TODO: Implement the structure members
};
Here's a well-structured Process definition that includes the necessary attributes for both FCFS (First Come First Served) and RR (Round Robin) scheduling algorithms:

cpp
Copy
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
Key attributes:

Basic attributes (used by both algorithms):

id: Unique identifier for each process

arrival_time: When the process enters the ready queue

burst_time: Total CPU time needed

RR-specific attributes:

remaining_time: Tracks how much CPU time is left (decremented during RR scheduling)

Metrics for analysis:

completion_time, turnaround_time, waiting_time - for performance evaluation

The constructor allows easy initialization, and the default constructor is provided for flexibility. This structure will work well with both scheduling approaches while providing all necessary metrics for comparing algorithm performance.

Would you like me to suggest any additional members or explain any part of this structure in more detail?

Can you now implement comparison for the priority queue for FCFS scheduling
stencil code:
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

// TODO: Implement comparison for the priority queue for FCFS scheduling
For FCFS (First-Come-First-Served) scheduling, we want the priority queue to order processes based on their arrival time (earlier arrivals get higher priority).

We can achieve this by defining a custom comparator for the priority queue. Since C++'s std::priority_queue is a max-heap by default, we need to invert the comparison to ensure the earliest arrival is at the top.

Implementation:
cpp
Copy
// Comparison struct for FCFS scheduling (orders processes by arrival_time)
struct CompareFCFS {
    bool operator()(const Process& p1, const Process& p2) {
        // Higher priority (top of the queue) goes to the earlier arrival
        return p1.arrival_time > p2.arrival_time;
    }
};
How to Use It:
When declaring the priority queue, specify the comparator:

cpp
Copy
std::priority_queue<Process, std::vector<Process>, CompareFCFS> fcfs_queue;
Full Updated Code:
cpp
Copy
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

// Example usage:
int main() {
    std::priority_queue<Process, std::vector<Process>, CompareFCFS> fcfs_queue;
    
    // Adding processes (id, arrival_time, burst_time)
    fcfs_queue.push(Process(1, 0, 5));  // Arrives first
    fcfs_queue.push(Process(2, 2, 3));  // Arrives later
    fcfs_queue.push(Process(3, 1, 4));  // Arrives in the middle

    // Processes will be ordered by arrival_time: 1, 3, 2
    while (!fcfs_queue.empty()) {
        Process p = fcfs_queue.top();
        std::cout << "Process " << p.id << " (Arrival: " << p.arrival_time << ")\n";
        fcfs_queue.pop();
    }

    return 0;
}
Output:
Copy
Process 1 (Arrival: 0)
Process 3 (Arrival: 1)
Process 2 (Arrival: 2)
Key Points:
The CompareFCFS functor ensures that the process with the earliest arrival time is always at the top.

This works because std::priority_queue uses a max-heap, so we reverse the comparison (>) to get a min-heap behavior for arrival times.

This is the correct ordering for FCFS scheduling.

Would you like me to extend this for Round Robin (RR) scheduling next?

Can you also show what global variables may be needed for shared resources amoung threads
For a multi-threaded CPU scheduler simulating FCFS and RR, we need shared resources to coordinate thread execution, manage the ready queue, and track scheduling metrics. Here are the key global variables you might need, along with synchronization primitives:

Global Variables for Thread-Safe Scheduling
cpp
Copy
#include <mutex>
#include <condition_variable>
#include <queue>
#include <vector>

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
Explanation of Each Global Variable
fcfs_queue & rr_queue

fcfs_queue: A priority queue sorted by arrival_time (FCFS).

rr_queue: A simple FIFO queue (Round Robin).

mtx (Mutex)

Ensures thread-safe access to shared data (queues, current_time, etc.).

cv (Condition Variable)

Used to notify worker threads when:

A new process arrives.

The scheduler switches algorithms.

all_processes_submitted

Set to true when no more processes will be added (prevents deadlocks).

current_time

Simulates a CPU clock for tracking arrivals, context switches, and completions.

time_quantum

The time slice for Round Robin (e.g., 2ms).

completed_processes

Stores finished processes to calculate metrics (avg. turnaround/waiting time).

Example Usage in Threads
Producer Thread (Adds Processes)
cpp
Copy
void producer() {
    std::vector<Process> processes = {
        {1, 0, 5},  // {id, arrival, burst}
        {2, 1, 3},
        {3, 2, 4}
    };

    for (auto& p : processes) {
        std::this_thread::sleep_for(std::chrono::milliseconds(p.arrival_time));
        
        std::lock_guard<std::mutex> lock(mtx);
        fcfs_queue.push(p);  // Add to FCFS queue
        rr_queue.push(p);    // Add to RR queue
        cv.notify_one();     // Wake up scheduler thread
    }

    // Signal that no more processes are coming
    std::lock_guard<std::mutex> lock(mtx);
    all_processes_submitted = true;
    cv.notify_all();
}
Consumer Thread (Scheduler)
cpp
Copy
void scheduler_fcfs() {
    while (true) {
        std::unique_lock<std::mutex> lock(mtx);
        cv.wait(lock, [] { 
            return !fcfs_queue.empty() || all_processes_submitted; 
        });

        if (fcfs_queue.empty() && all_processes_submitted) {
            break;  // No more work
        }

        if (!fcfs_queue.empty()) {
            Process p = fcfs_queue.top();
            fcfs_queue.pop();
            lock.unlock();  // Release lock during "execution"

            // Simulate execution (CPU burst)
            std::this_thread::sleep_for(std::chrono::milliseconds(p.burst_time));

            // Update completion time and metrics
            p.completion_time = current_time + p.burst_time;
            p.turnaround_time = p.completion_time - p.arrival_time;
            p.waiting_time = p.turnaround_time - p.burst_time;

            // Store completed process
            lock.lock();
            completed_processes.push_back(p);
            current_time = p.completion_time;
        }
    }
}
Key Synchronization Rules
Always lock mtx before accessing shared data.

Use cv.wait() to avoid busy waiting.

Unlock during CPU execution (no need to hold the lock while sleeping).

Set all_processes_submitted when done to prevent deadlocks.

Next Steps
Would you like me to:

Implement the Round Robin scheduler?

Add thread-safe statistics reporting?

Extend this with a hybrid FCFS+RR approach?

Let me know how you'd like to proceed!

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

// Simulate the execution of a process. This will be executed by each thread.
void executeProcess(int pid) {
    // TODO: Implement functionality for process execution simulation
    // Hint: You might need synchronization constructs to handle shared resources
    
    // Simulating process execution. You may need to replace the following line with actual computations or function calls representing the process's task.
    std::this_thread::sleep_for(std::chrono::seconds(1)); // Dummy execution time (you can adjust this as needed)
}

Can you show me how to implement the executeProcess function so it can be used by the threads without causing issues like deadlocks. Use mutex locks to protect this shared resource, ensuring no two threads can enter the critical section simultaneously.
Here's how to implement the executeProcess function with proper thread synchronization to prevent race conditions and deadlocks:

cpp
Copy
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
Key Features of This Implementation:
Thread-Safe Process Retrieval:

Uses std::unique_lock for mutex management

Searches both FCFS and RR queues safely

Proper Lock Management:

Releases lock during execution (sleep_for) to allow other threads to proceed

Reacquires lock to update shared state

Round Robin Support:

Implements time quantum slicing

Requeues unfinished processes

Completion Handling:

Calculates turnaround and waiting times

Updates completed processes list

Deadlock Prevention:

Never holds locks while sleeping

Uses condition variable to notify waiting threads

Usage Example:
cpp
Copy
int main() {
    // Add some processes
    {
        std::lock_guard<std::mutex> lock(mtx);
        fcfs_queue.push(Process(1, 0, 5));
        rr_queue.push(Process(1, 0, 5));
        fcfs_queue.push(Process(2, 1, 3));
        rr_queue.push(Process(2, 1, 3));
    }

    // Create worker threads
    std::thread t1(executeProcess, 1);
    std::thread t2(executeProcess, 2);

    t1.join();
    t2.join();

    // Print statistics
    std::cout << "\nCompleted processes:\n";
    for (const auto& p : completed_processes) {
        std::cout << "Process " << p.id 
                  << " - Turnaround: " << p.turnaround_time
                  << ", Waiting: " << p.waiting_time << "\n";
    }

    return 0;
}
Important Notes:
The mutex is released during the actual execution (sleep) to maximize concurrency

The linear search in RR queue is necessary because std::queue doesn't support random access

Error handling is included for cases where a process isn't found

All shared variable accesses are properly protected

Would you like me to modify any part of this implementation or add additional features?

Now can you complete the two scheduling functions, one for FCFS and one for RR
stencil:
// implement FCFS scheduling here
void firstComeFirstServed(/* TODO: Define parameters if needed */) {
    // TODO: Implement the FCFS scheduling algorithm.
    // Hint: You may need a data structure to hold your processes as they arrive and are scheduled for execution.
}

// implement Round Robin scheduling here
void roundRobin(/* TODO: Define parameters if needed */) {
    // TODO: Implement the Round Robin scheduling algorithm.
    // Hint: Consider how you will handle the time quantum and the scheduling queue.
}

Here's the complete implementation of both scheduling algorithms with proper thread synchronization:

cpp
Copy
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
Key Features:
FCFS Scheduler:

Processes are executed to completion in arrival order

Uses the priority queue (sorted by arrival time)

No preemption - once started, a process runs until done

Simple metrics calculation (turnaround = completion - arrival)

Round Robin Scheduler:

Processes execute for a fixed time quantum (2ms in this case)

Unfinished processes go back to the end of the queue

Implements preemptive scheduling

Tracks remaining time for each process

Properly handles process completion and requeueing

Common Thread Safety:

Both use unique_lock with condition variables

Mutex is released during execution (sleep)

Proper notification system with cv.notify_one()

Clean shutdown when all_processes_submitted is true

Usage Example:
cpp
Copy
int main() {
    // Create some test processes
    std::vector<Process> processes = {
        {1, 0, 6},  // ID, arrival, burst
        {2, 1, 4},
        {3, 2, 8},
        {4, 3, 2}
    };

    // Producer thread to add processes
    std::thread producer([&processes]() {
        for (auto& p : processes) {
            std::this_thread::sleep_for(std::chrono::milliseconds(p.arrival_time));
            
            std::lock_guard<std::mutex> lock(mtx);
            fcfs_queue.push(p);
            rr_queue.push(p);
            cv.notify_all();
            std::cout << "Added Process " << p.id << " at time " << current_time << "\n";
        }

        std::lock_guard<std::mutex> lock(mtx);
        all_processes_submitted = true;
        cv.notify_all();
    });

    // Start scheduler threads
    std::thread fcfs_thread(firstComeFirstServed);
    std::thread rr_thread(roundRobin);

    producer.join();
    fcfs_thread.join();
    rr_thread.join();

    // Print statistics
    std::cout << "\nScheduling Statistics:\n";
    for (const auto& p : completed_processes) {
        std::cout << "Process " << p.id 
                  << " - Turnaround: " << p.turnaround_time
                  << ", Waiting: " << p.waiting_time << "\n";
    }

    return 0;
}
Would you like me to add any additional features like:

Dynamic time quantum adjustment for RR?

Hybrid scheduling that switches between FCFS and RR?

More detailed statistics collection?

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

int main() {
    // TODO: Initialize process details. You might want to get these details from user input or a file.
    
    // TODO: Setup your environment - load processes, initialize variables, etc.

    // TODO: Start FCFS Scheduler. Make sure to signal threads to start when ready.

    // TODO: Reset the ready state for the next scheduling algorithm, if necessary.

    // TODO: Start Round Robin Scheduler. Consider how you'll manage the time quantum and signal threads.

    return 0; // Exit the program
}


Can you complete the main function so that it accepts input from a file or the command line and can successfully run the scheduling algorithms.

Here's the completed main() function that accepts input from either the command line or a file and runs both scheduling algorithms:

cpp
Copy
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
Key Features:
Command Line Interface:

-f filename to read from file

-q quantum to set RR time quantum

-h for help

Input Formats:

File format: One process per line (id arrival_time burst_time)

Interactive input: Type processes manually, end with "done"

Execution Flow:

Runs FCFS first, then RR with same processes

Clears state between schedulers

Proper synchronization throughout

Output:

Detailed execution trace

Final statistics table

Example Usage:
From file:

Copy
./scheduler -f processes.txt -q 3
Interactive:

Copy
./scheduler
Enter processes (id arrival_time burst_time), one per line.
Enter 'done' when finished.
1 0 5
2 1 3
3 2 4
done
Sample File (processes.txt):

Copy
1 0 6
2 1 4
3 2 8
4 3 2
This implementation provides a complete, production-ready scheduling simulation with proper error handling and user-friendly interfaces. Would you like me to add any additional features or modify any part of this implementation?