# Makefile for Go Sockets Lab — Full Testing with Unified Test Runner

BIN_DIR := bin
SERVER_BIN := $(BIN_DIR)/server
CLIENT_BIN := $(BIN_DIR)/client

.PHONY: all build test clean runserver runclient summary

# Default target
all: test

# Full test pipeline
test: build summary

# Build server and client binaries
build:
	@echo "Building server and client..."
	go build -o $(SERVER_BIN) ./server
	go build -o $(CLIENT_BIN) ./client

# Run integration tests, static checker, and print test summary
summary:
	@go run test_runner/test_runner.go

# Manual binary execution
runserver:
	@$(SERVER_BIN)

runclient:
	@$(CLIENT_BIN)

# Clean up everything no matter the OS! Holy moly (please test this on Windows more!)
clean:
	@echo "Cleaning up binaries and logs..."

	@if [ "$(OS)" = "Windows_NT" ]; then \
		echo "Detected Windows..."; \
		del /f /q $(SERVER_BIN).exe 2>nul || true; \
		del /f /q $(CLIENT_BIN).exe 2>nul || true; \
		del /f /q test_output.log 2>nul || true; \
	else \
		echo "Detected Unix-like system..."; \
		rm -f $(SERVER_BIN) $(CLIENT_BIN) test_output.log; \
	fi

