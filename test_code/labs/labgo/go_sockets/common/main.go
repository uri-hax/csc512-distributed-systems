// common/common.go
package common

import (
	"fmt"
	"os"
)

// TODO: put some cool stuff here! And maybe reuse some this?
const (
	IP_ADDRESS = ""
	PORT       = ""
)

// see how we reused this annoying function we write all the time?
func CheckArgs() {
	if len(os.Args) > 1 {
		fmt.Fprintln(os.Stderr, "You naughty little elf, this program takes no command-line arguments. :/")
		for i, arg := range os.Args {
			fmt.Fprintf(os.Stderr, "\targument %d: %s\n", i, arg)
		}
		os.Exit(1)
	}
}
