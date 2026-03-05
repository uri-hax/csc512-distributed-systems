# Debug Old Code (A2 & A3)

### Group Member's Name  
Gina Vincent  and Sophia Mancini

#### Program Name (A2 or A3)  
A2 - `sentence.c`  

#### Stack Layout

My partner and I used LLDB to inspect how local variables were allocated on the stack. Below is the backtrace (`bt`) output after running the program.  

Since Mac does not use GDB, my partner and I used **LLDB** instead:  

(lldb) bt

thread #1, queue = 'com.apple-main-thread', stop reason = breakpoint 1.1 frame #0: 0x000000010000366c sentence`main at sentence.c:10:5 7
8 int main() { 9 FILE *file; -> 10 char filename[] = "unix_sentence.text"; 11 char buffer[1024]; // Buffer to store data 12
13 // Open the file using the local fio library Target 0: (sentence) stopped.


#### Improvements and Debugging

**Describe the bugs you found?**  
After debugging the program, my partner and I determined that **no major bugs were present**.  

- The program successfully **opened and read** the file.  
- `fopen()` worked correctly, and `fgets()` **read input as expected**.  
- No **memory leaks, segmentation faults, or crashes** were detected.  

**Describe any unsafe code you found?**  
my partner and I initially considered some areas for potential improvement, but they did not cause any actual issues:  
- **Hardcoded File Path:**  
  ```c
  char filename[] = "unix_sentence.text";

**Describe one improvement made to the code**
After debugging, my partner and I determined that no changes were necessary because the program functioned correctly.  

- The program successfully opened and read the file without any issues.  
- There were no memory leaks, crashes, or unexpected behavior.  
- While some potential improvements (such as handling command-line arguments or adding additional error handling) were considered, they were not necessary for the program to function as intended.  

Since there were no critical bugs, my partner and I did not modify the original `sentence.c`.  

#### Fixing a Bug or Improving the Code

Since no modifications were needed, my partner and I did not implement any fixes.  

- **The original `sentence.c` worked correctly**, so no `sentence_original.c` was created.  
- **No lines were modified** because debugging confirmed that the existing implementation was correct. 

Copy your original code as NAME_original.c or NAME_original.cpp.

Implement a fix or improvement identified above. What lines was it implemented?

