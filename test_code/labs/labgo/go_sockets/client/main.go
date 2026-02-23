package main

import (
	"fmt"
	"net"
	"os"
)

func main() {
	// TODO: no CheckArgs() from common :/

	// net.Dial will fail our static_checker btw :/
	// TODO: create shared function in common ConnectToServer
	conn, err := net.Dial("tcp", "127.0.0.1:8080")
	if err != nil {
		fmt.Fprintln(os.Stderr, "Connection failed:", err)
		os.Exit(1)
	}
	defer conn.Close()

	// message := "CLIENT: I am sending a message!\n" // TODO: uncomment
	// reply, err := common.SendAndReceive(conn, message) // TODO implement and use

	// don't send or read anything meaningful -- ya basic
	fmt.Println("CLIENT: printing the buffer...")
}
