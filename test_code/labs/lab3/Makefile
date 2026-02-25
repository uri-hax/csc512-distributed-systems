# C++ Variables
CXX = g++
CXXFLAGS = -Wall -Wextra -Werror -pedantic -std=c++20 -g -O3
CPP_OBJECTS = tee.o
CPP_PROGRAMS = tee

# Rust Variables
RUSTC = rustc
RUST_PROGRAM = tee_rust
RUST_SRC = tee.rs

# Default target - only build C++ (Rust is optional)
all: $(CPP_PROGRAMS)

# Optional Rust target (only if rustc is available)
rust: $(RUST_PROGRAM)

# C++ Build Targets
tee: tee.o
	$(CXX) $(CXXFLAGS) -o tee tee.o 

tee.o: tee.cpp
	$(CXX) $(CXXFLAGS) -c tee.cpp

# Rust Build Targets (optional)
tee_rust: $(RUST_SRC)
	$(RUSTC) $(RUSTFLAGS) -o tee_rust $(RUST_SRC)

clean: 
	rm -f $(CPP_PROGRAMS) $(CPP_OBJECTS) $(RUST_PROGRAM)

.PHONY: all clean rust