CXX = g++
CC = gcc
CXXFLAGS = -Wall -Wextra -pedantic -std=c++20 -g -O3 -fsanitize=address -pthread
CFLAGS = -D_POSIX_C_SOURCE=200809L -Wall -Wextra -pedantic -std=c11 -g -O3

OBJECTS = main.o
PROGRAMS = main
TEST_PROGRAM = tests/test_log_files

all: $(PROGRAMS)

remake: clean main run tests

main: main.o
	$(CXX) $(CXXFLAGS) -o $@ $^

main.o: main.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

run: cleanlogs
	./main

tests: $(TEST_PROGRAM)
	./$(TEST_PROGRAM)

$(TEST_PROGRAM): tests/test_log_files.c
	rm -f $(TEST_PROGRAM)
	$(CC) $(CFLAGS) -o $(TEST_PROGRAM) $^

clean:
	rm -f $(PROGRAMS) $(OBJECTS) $(TEST_PROGRAM)

cleanlogs:
	test -d logFolder && rm -rf logFolder || true

.PHONY: all remake run tests clean cleanlogs