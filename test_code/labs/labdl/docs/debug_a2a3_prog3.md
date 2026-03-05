# Debug Old Code (A2 & A3)

### Group Member's Name

Gina Vincent & Sofia Mancini

#### Program Name (A2 or A3)

A3 (wc.cpp)

#### Stack Layout

csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog3$ gdb ./wc_original
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
Reading symbols from ./wc_original...
(gdb) break main
Breakpoint 1 at 0x1f60: file wc_original.cpp, line 43.
(gdb) step
The program is not being run.
(gdb) run
Starting program: /home/csc412-user/labs/labdl/old_code/prog3/wc_original 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=1, argv=0xfffffffff578) at wc_original.cpp:43
43      int main(int argc, char *argv[]) {
(gdb) bt
#0  main (argc=1, argv=0xfffffffff578) at wc_original.cpp:43
(gdb) step
44          int total_line_count = 0;
(gdb) step
45          int total_word_count = 0;
(gdb) step
46          int total_byte_count = 0;
(gdb) c
Continuing.
erv
ev
erfvewrv
^C
Program received signal SIGINT, Interrupt.
0x0000fffff7327d3c in __GI___libc_read (fd=0, buf=0xfffff3603780, nbytes=1024) at ../sysdeps/unix/sysv/linux/read.c:26
26      ../sysdeps/unix/sysv/linux/read.c: No such file or directory.
(gdb) bt
#0  0x0000fffff7327d3c in __GI___libc_read (fd=0, buf=0xfffff3603780, nbytes=1024) at ../sysdeps/unix/sysv/linux/read.c:26
#1  0x0000fffff72c6278 in _IO_new_file_underflow (fp=0xfffff73eb948 <_IO_2_1_stdin_>) at ./libio/libioP.h:947
#2  0x0000fffff72c72c0 in __GI__IO_default_uflow (fp=0xfffff73eb948 <_IO_2_1_stdin_>) at ./libio/libioP.h:947
#3  0x0000fffff710b4f8 in __gnu_cxx::stdio_sync_filebuf<char, std::char_traits<char> >::underflow() () from /lib/aarch64-linux-gnu/libstdc++.so.6
#4  0x0000fffff70be85c in std::basic_istream<char, std::char_traits<char> >& std::getline<char, std::char_traits<char>, std::allocator<char> >(std::basic_istream<char, std::char_traits<char> >&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, char) () from /lib/aarch64-linux-gnu/libstdc++.so.6
#5  0x0000aaaaaaaa3554 in std::getline<char, std::char_traits<char>, std::allocator<char> > (__str="", __is=...) at /usr/include/c++/11/bits/basic_string.h:6573
#6  process_in (input=..., filename="", total_line_count=<optimized out>, total_word_count=@0xfffffffff0f0: 3, total_byte_count=@0xfffffffff100: 16)
    at wc_original.cpp:12
#7  0x0000aaaaaaaa2bb4 in main (argc=<optimized out>, argv=<optimized out>) at wc_original.cpp:49
(gdb) c
Continuing.
ç
^C
Program received signal SIGINT, Interrupt.
0x0000fffff7327d3c in __GI___libc_read (fd=0, buf=0xfffff3603780, nbytes=1024) at ../sysdeps/unix/sysv/linux/read.c:26
26      in ../sysdeps/unix/sysv/linux/read.c
(gdb) q
A debugging session is active.

        Inferior 1 [process 1021] will be killed.

Quit anyway? (y or n) y
csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog3$ gdb ./wc_original
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
Reading symbols from ./wc_original...
(gdb) break main
Breakpoint 1 at 0x1f60: file wc_original.cpp, line 43.
(gdb) run test.txt
Starting program: /home/csc412-user/labs/labdl/old_code/prog3/wc_original test.txt
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=2, argv=0xfffffffff578) at wc_original.cpp:43
43      int main(int argc, char *argv[]) {
(gdb) bt
#0  main (argc=2, argv=0xfffffffff578) at wc_original.cpp:43
(gdb) c
Continuing.
4 4 8 test.txt
[Inferior 1 (process 1033) exited normally]
(gdb) run nofile.txt
Starting program: /home/csc412-user/labs/labdl/old_code/prog3/wc_original nofile.txt
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=2, argv=0xfffffffff568) at wc_original.cpp:43
43      int main(int argc, char *argv[]) {
(gdb) bt
#0  main (argc=2, argv=0xfffffffff568) at wc_original.cpp:43
(gdb) c
Continuing.
/home/csc412-user/labs/labdl/old_code/prog3/wc_original: nofile.txt: No such file or directory
[Inferior 1 (process 1035) exited normally]
(gdb) q
csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog3$ make clean
rm -f wc_original wc_optimized wc_original.o wc_optimized.o
csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog3$ 


#### Improvements and Debugging

**Describe the bugs you found?**

- In the main function, when the program encounters a missing file, it prints the error message incorrectly. Specifically, the error message uses argv[0] (the name of the program itself) instead of argv[i] (the name of the file that couldn't be opened). This was identified during debugging when the program failed to handle a missing file correctly, and the error message printed was: wc: nofile.txt: No such file or directory

- When processing multiple files, the code doesn't provide an overall summary of the total line, word, and byte counts until more than one file is processed. This might cause confusion if users expect the summary even for a single file.


**Describe any unsafe code you found?**

- The code assumes that argv[i] always refers to a valid file path or stdin. If the file path contains special characters, spaces, or non-printable characters, it could potentially cause issues.

**Describe one improvement made to the code**

- One improvement made to the code is correcting the error message for missing files. In the main function, the program now correctly prints:
wc: nofile.txt: No such file or directory
instead of printing the program's name (argv[0]). This makes the error message more informative and accurate for users who encounter missing file errors.

#### Fixing a Bug or Improving the Code

Copy your original code as NAME_original.c or NAME_original.cpp.

Implement a fix or improvement identified above. What lines was it implemented?

Byte Count: We account for the newline character by adding 1 byte for each line. [line 16]

Output for Multiple Files: After processing multiple files, it prints the cumulative totals (lines, words, and bytes) with the "total" label. [line 63]
