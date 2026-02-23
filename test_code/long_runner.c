#include <stdio.h>
#include <unistd.h>
#include <time.h>

int main() {
    printf("=== Long Running Program Started ===\n");
    printf("This program will run for 60 seconds\n");
    fflush(stdout);
    
    int total_seconds = 60;
    
    for (int i = 1; i <= total_seconds; i++) {
        printf("[%d/%d] Working... (PID: %d)\n", i, total_seconds, getpid());
        fflush(stdout);  // Force output immediately
        sleep(1);  // Sleep for 1 second
    }
    
    printf("=== Program Completed Successfully ===\n");
    return 0;
}