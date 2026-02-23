

package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
)

func main() {
	// TODO: use common.CheckArgs()
	// TODO: use common.StartTCPServer and common.GetPort()

	listener, err := net.Listen("tcp", ":8080") // forbidden!
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to start server:", err)
		os.Exit(1)
	}
	defer listener.Close()
	fmt.Println("Server is listening on port", "8080") // oh no hardcoding the port # is bad here

	// TODO: loop to accept multiple clients
	// loop and then use "go" to create multiple threads calling handConnection()
	conn, err := listener.Accept()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Accept failed:", err)
		os.Exit(1)
	}
	defer conn.Close()

	// TODO: move connection logic to local function handleConnection(conn)
	reader := bufio.NewReader(conn)
	msg, err := reader.ReadString('\n')
	if err != nil {
		fmt.Fprintln(os.Stderr, "Read error:", err)
		return
	}
	fmt.Println("SERVER: Received:", msg)

	// TODO: send newline-terminated response string
	response := "todo\n"
	_, err = conn.Write([]byte(response))
	if err != nil {
		fmt.Fprintln(os.Stderr, "Write error:", err)
		return
	}
}

/* TODO: uncomment and use locally
func handleConnection(conn net.Conn) {
	defer conn.Close()

	reader := bufio.NewReader(conn)
	msg, err := reader.ReadString('\n')
	if err != nil {
		fmt.Fprintln(os.Stderr, "Read error:", err)
		return
	}
	fmt.Println("SERVER: Received:", msg)

	response := "Hi I am a message from the server!\n"
	_, err = conn.Write([]byte(response))
	if err != nil {
		fmt.Fprintln(os.Stderr, "Write error:", err)
		return
	}
	fmt.Println("SERVER: Sent message to client")
}
*/
