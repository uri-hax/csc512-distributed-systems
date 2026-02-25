go mod init go_sockets

### Run Go Code
go run ./server
go run ./client


### Build Binaries and Run Binaries
Just running go build, will build the Go binary for the OS you are currently on.

```
go build -o server ./server && cp server/server bin/
go build -o client ./client && cp client/client bin/
```

The run these in separate terminals:
```
./bin/server
./bin/client 
```

Trying swithcing the order and see what happens:
```
./bin/client
./bin/server
```
