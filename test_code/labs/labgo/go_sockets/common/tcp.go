package common

import (
	"net"
)

/*
* return nil, nil in functions ensures it compiles ;)
 */

// TODO: replace this with actual implementation
func StartTCPServer(port string) (net.Listener, error) {
	return nil, nil
}

// TODO: replace this with actual implementation
func ConnectToServer(ip, port string) (net.Conn, error) {
	return nil, nil
}

// TODO: replace this with actual implementation
func SendAndReceive(conn net.Conn, msg string) (string, error) {
	return "", nil
}

// GOOD TO GO: basic helper for consistent fatal error handling
func FatalErr(msg string, err error) {
	// We left this function is left fully implemented
	// so you can use it to exit on fatal errors
	// Usage: FatalErr("message", err)
	println(msg, err)
}
