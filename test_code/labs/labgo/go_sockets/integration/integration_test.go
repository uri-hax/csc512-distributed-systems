package integration

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	"go_sockets/common"
)

func startServer(t *testing.T) *exec.Cmd {
	cmd := exec.Command("../bin/server")
	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start server: %v", err)
	}

	if err := waitForServer(); err != nil {
		t.Fatalf("server did not start listening in time: %v", err)
	}

	return cmd
}

func waitForServer() error {
	address := net.JoinHostPort(common.IP_ADDRESS, "8080")
	for i := 0; i < 20; i++ {
		conn, err := net.Dial("tcp", address)
		if err == nil {
			conn.Close()
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Errorf("server not reachable after 2 seconds")
}

func TestServerClientMessageExchange(t *testing.T) {
	server := startServer(t)
	defer server.Process.Kill()

	conn, err := common.ConnectToServer(common.IP_ADDRESS, "8080")
	if err != nil {
		t.Fatalf("connection failed: %v", err)
	}
	defer conn.Close()

	resp, err := common.SendAndReceive(conn, "ping\n")
	if err != nil {
		t.Fatalf("SendAndReceive failed: %v", err)
	}
	if !strings.Contains(resp, "Hi I am a message") {
		t.Errorf("unexpected response: %s", resp)
	}
}

func TestClientReceivesServerMessage(t *testing.T) {
	server := startServer(t)
	defer server.Process.Kill()

	client := exec.Command("../bin/client")
	output, err := client.CombinedOutput()
	if err != nil {
		t.Fatalf("client failed: %v\nOutput: %s", err, output)
	}
	if !strings.Contains(string(output), "Hi I am a message") {
		t.Errorf("expected message not found in client output: %s", output)
	}
}

func TestMultipleClientConnections(t *testing.T) {
	server := startServer(t)
	defer server.Process.Kill()

	for i := 0; i < 3; i++ {
		client := exec.Command("../bin/client")
		output, err := client.CombinedOutput()
		if err != nil {
			t.Errorf("client %d failed: %v\nOutput: %s", i, err, output)
		}
		if !strings.Contains(string(output), "Hi I am a message") {
			t.Errorf("client %d did not receive expected response: %s", i, string(output))
		}
	}
}

func TestClientReconnectAfterDrop(t *testing.T) {
	server := startServer(t)
	defer server.Process.Kill()

	conn, err := common.ConnectToServer(common.IP_ADDRESS, "8080")
	if err != nil {
		t.Fatalf("first connection failed: %v", err)
	}
	conn.Close()

	time.Sleep(100 * time.Millisecond) // brief pause between drops

	conn2, err := common.ConnectToServer(common.IP_ADDRESS, "8080")
	if err != nil {
		t.Fatalf("reconnection failed: %v", err)
	}
	defer conn2.Close()

	resp, err := common.SendAndReceive(conn2, "ping-again\n")
	if err != nil {
		t.Fatalf("SendAndReceive failed: %v", err)
	}
	if !strings.Contains(resp, "Hi I am a message") {
		t.Errorf("unexpected response after reconnect: %s", resp)
	}
}

// whaaaat why it is over 9000?
// your OS may take time to fully release the port (even after listener.Close()).
// aren't Networks complicated?
func TestServerFailsOnPortInUse(t *testing.T) {
	const conflictPort = "9090"

	listener, err := net.Listen("tcp", ":"+conflictPort)
	if err != nil {
		t.Fatalf("failed to bind port manually: %v", err)
	}
	defer listener.Close()

	server := exec.Command("../bin/server")
	server.Env = append(os.Environ(), "PORT="+conflictPort)

	err = server.Start()
	if err != nil {
		t.Fatalf("failed to start server process: %v", err)
	}

	// Wait for server to fail
	err = server.Wait()
	if err == nil {
		t.Fatal("expected server to fail due to port in use, but it exited successfully")
	}
}
