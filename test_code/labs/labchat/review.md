
## Expectations and Plan
My initial thoughts for this lab are that it will probably be frustrating. While I think AI is incredibly useful at *assisting* with checking and debugging code, from my experience, it does an extremely poor job of writing it. 

I've found that by breaking up prompts into smaller chunks, GenAI usually does a better job of completeing a task successfully than when given an entire program description. For this lab I will likely ask the AI to implement small pieces of the code at a time, this will 1. make it easier for me to review and catch any potential errors and 2. Break up the amount of work the AI needs to do at one time.


## Code Review (you review the code quality)

The code quality that deepseek created is actually quite good. The functions aren't overly complex or attempting to handle too much input in a single line. Without expressly prompting it to do so, the AI included several key checks and error calls that make the code more robust.There are a few changes and improvements I would make to this code. There is an error in the RR function that involves duplicated completions, which is effecting the metrics. I would also chose to simplify the main function. I would likely move the producer threads functionality and scheduling out of main to further modularize the code.
The AI provided examples for testing the algorthims both from the command line and from a file, example output:

    csc412-user@2ccd8c8e4c1b:~/labs/labchat$ make
    g++ -Wall -Wextra -pedantic -std=c++20 -g -O3 -c main.cpp -o main.o
    g++ -Wall -Wextra -pedantic -std=c++20 -g -O3 -o main main.o
    csc412-user@2ccd8c8e4c1b:~/labs/labchat$ ./main
    Enter processes (id arrival_time burst_time), one per line.
    Enter 'done' when finished.
    1 0 5
    2 1 3
    3 2 4
    done

    Starting FCFS Scheduling:
    Added Process 1 (arrival: 0, burst: 5)
    FCFS executing Process 1 for 5 units
    Added Process 2 (arrival: 1, burst: 3)
    Added Process 3 (arrival: 2, burst: 4)
    FCFS completed Process 1 at time 5
    FCFS executing Process 2 for 3 units
    FCFS completed Process 2 at time 8
    FCFS executing Process 3 for 4 units
    FCFS completed Process 3 at time 12
    FCFS scheduler exiting

    Starting Round Robin Scheduling (quantum = 2):
    RR executing Process 1 for 2 units
    RR requeued Process 1 (remaining: 3)
    RR executing Process 2 for 2 units
    RR requeued Process 2 (remaining: 1)
    RR executing Process 3 for 2 units
    RR requeued Process 3 (remaining: 2)
    RR executing Process 1 for 2 units
    RR requeued Process 1 (remaining: 3)
    RR executing Process 2 for 2 units
    RR requeued Process 2 (remaining: 1)
    RR executing Process 1 for 2 units
    RR requeued Process 1 (remaining: 1)
    RR executing Process 3 for 2 units
    RR requeued Process 3 (remaining: 2)
    RR executing Process 2 for 1 units
    RR completed Process 2 at time 15
    RR executing Process 3 for 2 units
    RR completed Process 3 at time 17
    RR executing Process 1 for 2 units
    RR requeued Process 1 (remaining: 1)
    RR executing Process 2 for 1 units
    RR completed Process 2 at time 20
    RR executing Process 1 for 1 units
    RR completed Process 1 at time 21
    RR executing Process 3 for 2 units
    RR completed Process 3 at time 23
    RR executing Process 1 for 1 units
    RR completed Process 1 at time 24
    RR scheduler exiting

    Scheduling Statistics:
    Process ID | Turnaround Time | Waiting Time
        2     |       14       |      11
        3     |       15       |      11
        2     |       19       |      16
        1     |       21       |      16
        3     |       21       |      17
        1     |       24       |      19
    csc412-user@2ccd8c8e4c1b:~/labs/labchat$ make clean
    rm -rf logFolder
    rm -f main main.o 

The code successfully is able to handle processes and compiles and runs without warnings or errors.

## Self-Reflection

My initial plan to request small components from the AI instead of the entire program seemed to work effectively as with relatively little input I was able to produce a working program. 

## Compare Algorithms

### FCFS
- Pros: No overhead from context-switching
- Cons: Poor results for longer processes, highly biases based on arrival order.
- Best for: Processes with similar execution times

### RR
- Example was done with a time quanta = 2
- Pros: Fair to all processes, regardless of arrival time
- Cons: High overhead (context switches) which can increase turnaround time
- Best for: Interactive systems

FCFS would be best use for things such as rendering or scientific computations, while RR is ideal for user-facing apps and real-time tasks.

Changing the time quanta would make the RR more efficient by reducing overhead. Fixing the big in RR would also improve the metrics.

## Technical Concepts
1. Process Scheduling - Determining the order of process execution by the CPU.
2. FCFS (First-Come-First-Served) - A scheduling algorithm that executes processes in their arrival order.
3. RR (Round Robin) - A preemptive scheduling algorithm that assigns fixed time slices to each process.
4. Thread Synchronization - Coordinating thread execution to prevent race conditions.
5. Mutex (Mutual Exclusion) - A synchronization primitive that protects shared resources from concurrent access.
6. Condition Variables - Thread signaling mechanisms that enable efficient waiting/notification.
7. Context Switching - The process of saving/restoring thread states when switching execution.
8. Time Quantum - The fixed time slice allocated to each process in Round Robin scheduling.
9. Turnaround Time - Total time taken from process submission to completion.
10. Waiting Time - Time a process spends waiting in the ready queue.
11. Preemptive Scheduling - Temporarily interrupting processes to allocate CPU fairly.
12. Non-preemptive Scheduling - Allowing processes to run uninterrupted until completion.
13. Thread-safe Data Structures - Shared queues protected against concurrent access.
14. Producer-Consumer Pattern - A design where one thread generates tasks and others execute them.
15. CPU Burst Time - The execution time required by a process before I/O or completion.