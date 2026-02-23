// common/check-forbidden.go
package main

import (
	"fmt"
	"os"
	"strings"
)

func checkFile(path string, forbidden []string) bool {
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "could not read file: %s\n", path)
		return false
	}
	for _, keyword := range forbidden {
		if strings.Contains(string(data), keyword) {
			fmt.Fprintf(os.Stderr, "ERROR: ❌ Forbidden usage of %q in %s\n", keyword, path)
			return true
		}
	}
	return false
}

func main() {
	fail := false

	if checkFile("client/main.go", []string{"net.Dial", "net.DialTCP"}) {
		fail = true
	}
	if checkFile("server/main.go", []string{"net.Listen", "net.ListenTCP"}) {
		fail = true
	}

	if fail {
		fmt.Println("STATIC_CHECK: FAIL")
		os.Exit(1)
	}

	fmt.Println("✅ No forbidden API usage detected.")
	fmt.Println("STATIC_CHECK: PASS")
}
