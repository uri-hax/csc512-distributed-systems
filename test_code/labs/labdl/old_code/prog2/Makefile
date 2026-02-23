# C++ Variables
CXX = g++
CXXFLAGS = -Wall -Wextra -fsanitize=address -std=c++20 -g -O3
CPP_OBJECTS = wc_original.o wc_optimized.o
CPP_PROGRAMS = wc_original wc_optimized

all: $(CPP_PROGRAMS)

wc_optimized: wc_optimized.o
	$(CXX) $(CXXFLAGS) -o wc_optimized wc_optimized.o

wc_original: wc_original.o
	$(CXX) $(CXXFLAGS) -o wc_original wc_original.o

clean:
	rm -f $(CPP_PROGRAMS) $(CPP_OBJECTS)


