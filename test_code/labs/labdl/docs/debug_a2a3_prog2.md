# Debug Old Code (A2 & A3)

### Group Member's Name

Gina Vincent & Sofia Mancini

#### Program Name (A2 or A3)

A3 (wc.cpp)

#### Stack Layout

csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog2$ make
g++ -Wall -Wextra -fsanitize=address -std=c++20 -g -O3   -c -o wc.o wc.cpp
g++ -Wall -Wextra -fsanitize=address -std=c++20 -g -O3 -o wc wc.o
csc412-user@2ccd8c8e4c1b:~/labs/labdl/old_code/prog2$ gdb ./wc
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
Reading symbols from ./wc...
(gdb) break main
Breakpoint 1 at 0x2320: file wc.cpp, line 28.
(gdb) step
The program is not being run.
(gdb) run
Starting program: /home/csc412-user/labs/labdl/old_code/prog2/wc 
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=1, argv=0xfffffffff588) at wc.cpp:28
28      int main(int argc, char* argv[]) {
(gdb) bt
#0  main (argc=1, argv=0xfffffffff588) at wc.cpp:28
(gdb) step
29          int total_lines = 0, total_words = 0, total_bytes = 0;
(gdb) step
31          if (argc == 1) {
(gdb) step
33              count_file(std::cin, "(stdin)", total_lines, total_words, total_bytes);
(gdb) step
std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::basic_string<std::allocator<char> > (__a=..., __s=0xaaaaaaaa4aa0 "(stdin)", 
    this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.h:534
534           : _M_dataplus(_M_local_data(), __a)
(gdb) bt
#0  std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::basic_string<std::allocator<char> > (__a=..., __s=0xaaaaaaaa4aa0 "(stdin)", 
    this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.h:534
#1  main (argc=1, argv=<optimized out>) at wc.cpp:33
(gdb) step
std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_Alloc_hider::_Alloc_hider (__a=..., __dat=0xfffffffff130 "\270\362\377\377\377\377", 
    this=0xfffffffff120) at /usr/include/c++/11/ext/new_allocator.h:82
82            new_allocator(const new_allocator&) _GLIBCXX_USE_NOEXCEPT { }
(gdb) step
534           : _M_dataplus(_M_local_data(), __a)
(gdb) step
0x0000aaaaaaaa2e10 in std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_Alloc_hider::_Alloc_hider (__a=..., 
    __dat=0xfffffffff130 "\270\362\377\377\377\377", this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.h:165
165             : allocator_type(__a), _M_p(__dat) { }
(gdb) step
std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::basic_string<std::allocator<char> > (__a=..., __s=0xaaaaaaaa4aa0 "(stdin)", this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.h:539
539             _M_construct(__s, __end, random_access_iterator_tag());
(gdb) step
std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_M_construct<char const*> (__end=0xaaaaaaaa4aa7 "", __beg=0xaaaaaaaa4aa0 "(stdin)", 
    this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.tcc:225
225               { this->_S_copy_chars(_M_data(), __beg, __end); }
(gdb) step
std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >::_M_data (this=0xfffffffff120) at /usr/include/c++/11/bits/basic_string.h:194
194           _M_data() const
(gdb) c
Continuing.
wedq
qwervfqe
erfq
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
#5  0x0000aaaaaaaa3964 in std::getline<char, std::char_traits<char>, std::allocator<char> > (__str="", __is=...) at /usr/include/c++/11/bits/basic_string.h:6573
#6  count_file (input=..., filename="(stdin)", total_lines=@0xfffffffff0f0: 0, total_words=@0xfffffffff100: 0, total_bytes=@0xfffffffff110: 0) at wc.cpp:12
#7  0x0000aaaaaaaa2ea0 in main (argc=<optimized out>, argv=<optimized out>) at wc.cpp:33
(gdb) run test.txt
The program being debugged has been started already.
Start it from the beginning? (y or n) y
Starting program: /home/csc412-user/labs/labdl/old_code/prog2/wc test.txt
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/aarch64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=2, argv=0xfffffffff588) at wc.cpp:28
28      int main(int argc, char* argv[]) {
(gdb) bt
#0  main (argc=2, argv=0xfffffffff588) at wc.cpp:28
(gdb) c
Continuing.
4 4 8 test.txt
[Inferior 1 (process 974) exited normally]


#### Improvements and Debugging

**Describe the bugs you found?**

Input Handling Bug: Function doesn't handle std::cin input properly. When stepping through the code, the program pauses at std::getline() and waits for user input. If no input is provided, the program hangs, which can be seen when the program was interrupted using SIGINT. This can be problematic if the user forgets to provide input, leading to a non-terminating program.

File Processing Bug: Nonexistent files return 0 0 0 total and prints error message only to stderr.

**Describe any unsafe code you found?**

The program uses the argv array to handle the command-line arguments, but there seems to be potential issues with the argument validation (e.g., checking for null pointers or valid data). If argc or argv are not properly checked, it could lead to unsafe behavior like dereferencing invalid pointers, leading to segmentation faults or memory corruption.

**Describe one improvement made to the code**

File Processing Behavior: From the provided output, when the program was run with a file (test.txt), it worked as expected, producing output like 4 4 8 test.txt. The code improvement could be in how files are processed by ensuring that proper error handling is in place (e.g., checking if the file exists, if it's empty, or if the program has read permissions). This would make the program more robust when handling files, preventing possible crashes when the program is provided with invalid or unreadable files.

#### Fixing a Bug or Improving the Code

Copy your original code as NAME_original.c or NAME_original.cpp.

Implement a fix or improvement identified above. What lines was it implemented?

- The error message for missing files now uses argv[0] to include the program’s name in the error message. This helps when the program is called in different contexts or from different directories. [line 39]