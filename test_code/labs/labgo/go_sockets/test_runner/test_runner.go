package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func runCommand(name string, args ...string) (output []string, err error) {
	cmd := exec.Command(name, args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	scanner := bufio.NewScanner(stdout)
	lines := []string{}
	for scanner.Scan() {
		line := scanner.Text()
		lines = append(lines, line)
		fmt.Println(line) // real-time output
	}

	errOutput := bufio.NewScanner(stderr)
	for errOutput.Scan() {
		line := errOutput.Text()
		lines = append(lines, line)
		fmt.Println(line)
	}

	if err := cmd.Wait(); err != nil {
		return lines, err
	}

	return lines, nil
}

func main() {
	// integration tests
	fmt.Println("Running integration tests...")
	intLines, _ := runCommand("go", "test", "-v", "./integration")

	// our static checker
	fmt.Println("Running static checker...")
	staticLines, _ := runCommand("go", "run", "static_checker/check_forbidden.go")

	// combine logs from both and write to file
	logFile, _ := os.Create("test_output.log")
	defer logFile.Close()
	for _, l := range append(intLines, staticLines...) {
		fmt.Fprintln(logFile, l)
	}

	// lets get some results
	intPasses := 0
	intFails := 0
	staticCheckPass := false

	for _, line := range intLines {
		if strings.HasPrefix(line, "--- PASS") {
			intPasses++
		}
		if strings.HasPrefix(line, "--- FAIL") {
			intFails++
		}
	}

	for _, line := range staticLines {
		if strings.Contains(line, "STATIC_CHECK: PASS") {
			staticCheckPass = true
		}
	}

	fmt.Println("\n===== GO SOCKETS LAB TEST SUMMARY =====")
	fmt.Printf("Integration Tests: %d passed, %d failed\n", intPasses, intFails)
	fmt.Printf("Static Checker: %s\n", map[bool]string{true: "PASS", false: "FAIL"}[staticCheckPass])
	fmt.Println("----------------------------------------")

	total := 7
	passed := intPasses
	if staticCheckPass {
		passed += 2
	}

	fmt.Printf("PASSED: %d\n", passed)
	fmt.Printf("Total Tests: %d\n", total)

	if passed == total {
		fmt.Println("\nAll tests passed.")
		os.Exit(0)
	} else {
		fmt.Println("\nSome checks failed. See above for details.")
		os.Exit(1)
	}
}
