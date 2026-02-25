CFLAGS = -Wall -Wextra -fsanitize=address -g
CC = gcc

PROGS = fsrecursive lowercase makewords mismatch sentence sort unique  # Each program has its own main

all: $(PROGS)

%: %.c fio.o
	$(CC) $(CFLAGS) $^ -o $@

fio.o: fio.c
	$(CC) $(CFLAGS) -c fio.c -o fio.o

clean:
	rm -f $(PROGS) fio.o *.o
