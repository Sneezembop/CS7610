package main

import (
    "bufio"
    "encoding/gob"
    "flag"
    "io"
    "strings"
    "sync"
    "log"
    "net"
)

type complexData struct {
    N int
    S string
    M map[string] int
    P []byte
    C *complexData
}

const (
    Port = ":5501"
)

type HandleFunc func(writer *bufio.ReadWriter)

type Endpoint struct {
    listener net.Listener
    handler map[string]HandleFunc
    m sync.RWMutex
}

func NewEndpoint() *Endpoint {
    return &Endpoint{
        handler: map[string]HandleFunc{},
    }
}

func (e *Endpoint) AddHandleFunc (name string, f HandleFunc){
    e.m.Lock()
    e.handler[name] = f
    e.m.Unlock()

    return
}

func (e *Endpoint) Listen() error {
    var err error
    e.listener, err = net.Listen("tcp", Port)
    if err != nil {
        return err
    }
    log.Println("Listen on", e.listener.Addr().String())
    for {
        log.Println("Accept a connection request.")
        conn, err := e.listener.Accept()
        if err != nil {
            log.Println("Failed accepting a connection request:", err)
            continue
        }
        log.Println("Handle incoming messages.")
        go e.handleMessages(conn)
    }

    return nil
}

func (e *Endpoint) handleMessages (conn net.Conn){
    rw := bufio.NewReadWriter(bufio.NewReader(conn), bufio.NewWriter(conn))
    defer conn.Close()

    for {
        log.Print("Recieve Command '")
        cmd, err := rw.ReadString('\n')
        switch {
        case err == io.EOF:
            log.Println("Reached EOF - close this connection.\n  ---")
            return
        case err != nil:
            log.Println("\nError reading command. Got: '"+cmd+"'\n", err)
            return
        }

        cmd = strings.Trim(cmd, "\n")
        log.Println(cmd + "'")

        e.m.RLock()
        handleCommand, ok := e.handler[cmd]
        e.m.RUnlock()

        if !ok {
            log.Println("command '" + cmd + "' is not registered.")
            return
        }

        handleCommand(rw)
    }

    return
}

func handleStrings(rw *bufio.ReadWriter) {
    log.Print("Recieve STRING message:")
    s, err := rw.ReadString('\n')
    if err != nil {
        log.Println("Cannot read from connection.\n", err)
    }
    s = strings.Trim(s, "\n")
    log.Println(s)

    _, err = rw.WriteString("Thank you.\n")
    if err != nil {
        log.Println("cannot write to connection.\n", err)

    }
    err = rw.Flush()
    if err != nil {
        log.Println("Flush Failed.", err)
    }
    return
}

func handleGob(rw *bufio.ReadWriter) {
    log.Print("Recieve GOB data:")
    var data complexData
    dec := gob.NewDecoder(rw)
    err := dec.Decode(&data)
    if err != nil {
        log.Println("Error deconding GOB data:", err)
        return
    }

    log.Printf("Outer complexData struct: \n%#v\n", data)
    log.Printf("Inner complexData struct: \n%#v\n", data.C)
    return
}


func client(ip string) error {
    testStruct := complexData{
        N: 23,
        S: "string data",
        M: map[string]int{"one": 1, "two": 2, "three": 3},
        P: []byte("abc"),
        C: &complexData{
            N: 256,
            S: "Recursive structs? Piece of cake!",
            M: map[string]int{"01": 1, "10": 2, "11": 3},
        },
    }

    rw, err:= Open(ip + Port)
    if err != nil {
        return err
    }

    log.Println("Send the string request.")
    n, err := rw.WriteString("STRING\n")
    if err != nil {
        log.Println(n)
        return err
    }
    n, err = rw.WriteString("Additional data.\n")
    if err != nil {
        log.Println(n)
        return err
    }
    log.Println("Flush the buffer.")
    err = rw.Flush()
    if err != nil {
        log.Println(n)
        return err
    }

    log.Println("Read the reply." )
    response, err := rw.ReadString('\n')
    if err != nil {
        return err
    }

    log.Println("STRING request: got a response: ", response)

    log.Println("Send a struct as GOB:")
    log.Printf("Outer complexData struct: \n%#v\n", testStruct)
    log.Printf("Inner complexData struct: \n%#v\n", testStruct.C)
    enc := gob.NewEncoder(rw)

    n, err = rw.WriteString("GOB\n")
    if err != nil {
        return err
    }

    err = enc.Encode(testStruct)
    if err != nil {
        return err
    }

    err = rw.Flush()
    if err != nil {
        return err
    }

    return nil
}

func server() error {
    endpoint := NewEndpoint()
    endpoint.AddHandleFunc("STRING", handleStrings)
    endpoint.AddHandleFunc("GOB", handleGob)
    return endpoint.Listen()
}

func init() {
    log.SetFlags(log.Lshortfile)
    return
}

func main() {

    connect := flag.String("connect", "", "IP address of process to join. If empty, go into listen mode.")
    flag.Parse()

    if *connect != ""{
        err := client(*connect)
        if err != nil{
            log.Println("Error:", err)
        }
        log.Println("Client done.")
        return
    }

    err := server()
    if err != nil {
        log.Println("Error: ", err)
    }

    log.Println("Server done.")
    return
}

func Open(addr string) (*bufio.ReadWriter, error) {

    log.Println("Dial" + addr)
    conn, err := net.Dial("tcp", addr)
    if err != nil {
        log.Println("Dialing " + addr + " failed")
        log.Println(err)
        return nil, err
    }

    return bufio.NewReadWriter(bufio.NewReader(conn), bufio.NewWriter(conn)), nil

}
