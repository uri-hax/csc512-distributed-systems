# Debug Insecure Code

### Stack Trace

##### Results with gets()

csc412-user@2ccd8c8e4c1b:~/labs/labdl/insecure$ make
rm -f main
gcc -fsanitize=address -g -fno-stack-protector -o main main.c
main.c: In function ‘main’:
main.c:36:9: warning: implicit declaration of function ‘gets’; did you mean ‘fgets’? [-Wimplicit-function-declaration]
   36 |         gets(buffer); // FYI never use gets() in real production code!
      |         ^~~~
      |         fgets
/usr/bin/ld: /tmp/ccNt8514.o: in function `main':
/home/csc412-user/labs/labdl/insecure/main.c:36: warning: the `gets' function is dangerous and should not be used.
make: *** No rule to make target 'run', needed by 'remake'.  Stop.
csc412-user@2ccd8c8e4c1b:~/labs/labdl/insecure$ gdb ./main
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04.2) 12.1
Copyright (C) 2022 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
Type "show copying" and "show warranty" for details.
This GDB was configured as "aarch64-linux-gnu".
Type "show configuration" for configuration details.
For bug reporting instructions, please see:
<https://www.gnu.org/software/gdb/bugs/>.
Find the GDB manual and other documentation resources online at:
    <http://www.gnu.org/software/gdb/documentation/>.

For help, type "help".
Type "apropos word" to search for commands related to "word"...
Reading symbols from ./main...
(gdb) run
Starting program: /home/csc412-user/labs/labdl/insecure/main 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Detaching after fork from child process 852]
Enter some text: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Mem not shared. 9
Mem shared. 5
[Inferior 1 (process 850) exited normally]
(gdb) set follow-fork-mode child
(gdb) b gets
Breakpoint 1 at 0xfffff72ba450: file ./libio/iogets.c, line 37.
(gdb) run
Starting program: /home/csc412-user/labs/labdl/insecure/main 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Attaching after Thread 0xfffff7fc0440 (LWP 853) fork to child process 854]
[New inferior 2 (process 854)]
[Detaching after fork from parent process 853]
[Inferior 1 (process 853) detached]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Switching to Thread 0xfffff7fc0440 (LWP 854)]

Thread 2.1 "main" hit Breakpoint 1, _IO_gets (buf=0xfffffffff410 "0\364\377\377\377\377") at ./libio/iogets.c:37
37      ./libio/iogets.c: No such file or directory.
(gdb) bt
#0  _IO_gets (buf=0xfffffffff410 "0\364\377\377\377\377") at ./libio/iogets.c:37
#1  0x0000aaaaaaaa1090 in main (argc=1, argv=0xfffffffff5a8) at main.c:36
(gdb) c
Continuing.
Enter some text: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
[Inferior 2 (process 854) exited normally]
(gdb) Mem not shared. 9
Mem shared. 5

##### Results with fgets()

csc412-user@2ccd8c8e4c1b:~/labs/labdl/insecure$ make
rm -f main
gcc -fsanitize=address -g -fno-stack-protector -o main main.c
make: *** No rule to make target 'run', needed by 'remake'.  Stop.
csc412-user@2ccd8c8e4c1b:~/labs/labdl/insecure$ gdb ./main
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04.2) 12.1
Copyright (C) 2022 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
Type "show copying" and "show warranty" for details.
This GDB was configured as "aarch64-linux-gnu".
Type "show configuration" for configuration details.
For bug reporting instructions, please see:
<https://www.gnu.org/software/gdb/bugs/>.
Find the GDB manual and other documentation resources online at:
    <http://www.gnu.org/software/gdb/documentation/>.

--Type <RET> for more, q to quit, c to continue without paging--c
For help, type "help".
Type "apropos word" to search for commands related to "word"...
Reading symbols from ./main...
(gdb) run
Starting program: /home/csc412-user/labs/labdl/insecure/main 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Detaching after fork from child process 902]
Enter some text: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Mem not shared. 9
Mem shared. 5
[Inferior 1 (process 900) exited normally]
(gdb) set follow-fork-mode child
(gdb) b fgets
Breakpoint 1 at 0xfffff72b90f0: fgets. (2 locations)
(gdb) run
Starting program: /home/csc412-user/labs/labdl/insecure/main 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Attaching after Thread 0xfffff7fc0440 (LWP 903) fork to child process 904]
[New inferior 2 (process 904)]
[Detaching after fork from parent process 903]
[Inferior 1 (process 903) detached]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".
[Switching to Thread 0xfffff7fc0440 (LWP 904)]

Thread 2.1 "main" hit Breakpoint 1, __interceptor_fgets (s=0xfffffffff410 "0\364\377\377\377\377", size=16, file=0xfffff73eb948 <_IO_2_1_stdin_>) at ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1251
1251    ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc: No such file or directory.
(gdb) bt
#0  __interceptor_fgets (s=0xfffffffff410 "0\364\377\377\377\377", size=16, file=0xfffff73eb948 <_IO_2_1_stdin_>)
    at ../../../../src/libsanitizer/sanitizer_common/sanitizer_common_interceptors.inc:1251
#1  0x0000aaaaaaaa1148 in main (argc=1, argv=0xfffffffff5a8) at main.c:39
(gdb) c
Continuing.

Thread 2.1 "main" hit Breakpoint 1, _IO_fgets (buf=0xfffffffff410 "0\364\377\377\377\377", n=16, fp=0xfffff73eb948 <_IO_2_1_stdin_>) at ./libio/iofgets.c:37
37      ./libio/iofgets.c: No such file or directory.
(gdb) c
Continuing.
Enter some text: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
[Inferior 2 (process 904) exited normally]
Mem not shared. 9
Mem shared. 5

##### Describe the differences between the stack traces

The gets() version directly calls _IO_gets, which is flagged as dangerous. The warning during compilation states that gets() is unsafe due to its lack of bounds checking, making it susceptible to buffer overflows.
The fgets() version calls __interceptor_fgets, which is provided by AddressSanitizer, followed by _IO_fgets. Unlike gets(), fgets() takes a buffer size parameter, preventing buffer overflows.

In the gets() stack trace, the function _IO_gets is called directly in main() at main.c:36, showing a single function call before returning control to main().
In the fgets() stack trace, fgets() first goes through __interceptor_fgets (an AddressSanitizer wrapper), then _IO_fgets, indicating that additional security checks are being applied before executing the standard library function.

When setting a breakpoint at gets(), execution immediately pauses at _IO_gets.
When setting a breakpoint at fgets(), execution pauses at __interceptor_fgets first before reaching _IO_fgets, demonstrating that fgets() undergoes additional processing before executing.
Impact on Input Handling:

gets() allows unrestricted input, leading to potential buffer overflows if the input exceeds the allocated buffer.
fgets() enforces a size limit, ensuring that only a controlled amount of input is read, mitigating overflow risks.

### Develop your Intuition

Answer the questions below as a group.

##### Describe steps on how to recreate to a buffer overflow when gets() is used.

1. Create a buffer: define a character array of fixed size (char buffer[16])
2. Call gets(): Use gets(buffer) to read from stdin
3. Input > 16 chars: 'qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq'
4. Observe memory corruption: The extra characters overwrite in memory, and can cause memory corruption since gets() does not perform bounds checking.

##### Describe the change in values of buffer, shared_memory, and m as a result of overflow.

- buffer: Overwrites its allocated space and spills into adjacent memory locations
- shared_memory: has potential to be modified due to overwrite issues
- m: Could be altered unintentionally since it is stored after buffer and an overflow can change its calue.

##### Provide a short intuitive explanation of how gets() causes an error and how fgets() fixes this. 

- gets() reads the input without observing the file size, leading to overflow errors and memory corruption.
- fgets() limits the input size to the buffer size, stopping any overflow errors.

##### Provide a short intuitive explanation of how GDB to analyze programs with parent/child processes and shared_memory.

- Set breakpoints: use break to stop at specific locations in code, allowing for process creation to be observed.
- Step through execution: use step or next to track parent and child process execution.
- Inspect memory: examine shared memory values
- Follow process execution: follow memory layout