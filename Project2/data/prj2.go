package main

import (
	"bufio"
	"encoding/csv"
	"encoding/gob"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type peer struct {
	Port string
	Ip   string
	Id   int
	// rw bufio.ReadWriter
}

type view struct {
	Viewid  int
	Leader  *peer
	Members []peer
}

type opType int
type message int

const (
	ADD       opType  = 0
	DEL       opType  = 1
	PENDING   opType  = 2
	REQ       message = 0
	OK        message = 1
	NEWVIEW   message = 2
	NEWLEADER message = 3
)

type operation struct {
	Op     opType
	ReqId  int
	View   view
	OKs    []peer
	peerId int
}

type reqMessage struct {
	ReqId  int
	ViewId int
	Op     opType
	PeerId int
}

type okMessage struct {
	ReqId  int
	ViewId int
	PeerId int
}

type newViewMessage struct {
	ReqId   int
	NewView view
}

type heartBeatMessage struct {
	PeerId int
}

type newLeaderMessage struct {
	PeerId int
}

var myself peer

var myview view

var masterList view

var heartbeats []peer

var reqCount int

var verbose = false

var pendingOperations []operation

const (
	globalTimeout    = time.Second * 4
	allowedBadHearts = 2
)

type HandleFunc func(writer *bufio.ReadWriter)

type Endpoint struct {
	listener net.Listener
	handler  map[string]HandleFunc
	m        sync.RWMutex
}

func NewEndpoint() *Endpoint {
	return &Endpoint{
		handler: map[string]HandleFunc{},
	}
}

func (e *Endpoint) AddHandleFunc(name string, f HandleFunc) {
	e.m.Lock()
	e.handler[name] = f
	e.m.Unlock()

	return
}

func (e *Endpoint) Listen() error {
	var err error
	e.listener, err = net.Listen("tcp", myself.Port)
	if err != nil {
		return err
	}
	logString("Listen on", e.listener.Addr().String())
	for {
		logString("Accept a connection request.")
		conn, err := e.listener.Accept()
		if err != nil {
			logString("Failed accepting a connection request:", err)
			continue
		}
		conn.SetDeadline(time.Now().Add(globalTimeout))
		logString("Handle incoming messages.")
		go e.handleMessages(conn)
	}

	return nil
}

func (e *Endpoint) handleMessages(conn net.Conn) {
	rw := bufio.NewReadWriter(bufio.NewReader(conn), bufio.NewWriter(conn))
	defer conn.Close()

	for {
		logString("Recieve Command '")
		cmd, err := rw.ReadString('\n')

		switch {
		case err == io.EOF:
			logString("Reached EOF - close this connection.\n  ---")
			return

		case err != nil:
			logString("\nError reading command. Got: '"+cmd+"'\n", err)
			return
		}

		cmd = strings.Trim(cmd, "\n")
		logString(cmd + "'")

		e.m.RLock()
		handleCommand, ok := e.handler[cmd]
		e.m.RUnlock()

		if !ok {
			logString("command '" + cmd + "' is not registered.")
			return
		}

		handleCommand(rw)
	}

	return
}

func handleReq(rw *bufio.ReadWriter) {

	logString("REQ RECIEVED")
	var message reqMessage
	dec := gob.NewDecoder(rw)
	err := dec.Decode(&message)
	if err != nil {
		logString("Error decoding GOB REQ message data:", err)
		return
	}

	logString(message)

	newOp := operation{
		Op:     message.Op,
		ReqId:  message.ReqId,
		View:   myview,
		OKs:    []peer{},
		peerId: message.PeerId,
	}

	pendingOperations = append(pendingOperations, newOp)

	sendMessage(*myview.Leader, okMessage{message.ReqId, myview.Viewid, myself.Id})

	return
}

func handleOK(rw *bufio.ReadWriter) {
	logString("OK RECIEVED")
	var message okMessage
	dec := gob.NewDecoder(rw)
	err := dec.Decode(&message)
	if err != nil {
		logString("Error decoding GOB OK message data:", err)
		return
	}

	logString(message)

	//logString(pendingOperations)

	for _, ops := range pendingOperations {
		if (ops.ReqId == message.ReqId) && (ops.View.Viewid == message.ViewId) {
			apeer := getPeerById(message.PeerId)
			ops.OKs = append(ops.OKs, apeer)

			logString("New Op Update:")
			logString(ops)

			if len(ops.OKs) == (len(ops.View.Members)-1) && ops.Op == ADD {
				pushAddOp(ops.peerId)
			}

			if len(ops.OKs) == (len(ops.View.Members)-2) && ops.Op == DEL {
				pushDelOp(ops.peerId)
			}

		}
	}

	return
}

func pushAddOp(peerId int) {

	newPeer := getPeerById(peerId)

	newView := view{
		Viewid:  myview.Viewid + 1,
		Leader:  myview.Leader,
		Members: append(myview.Members, newPeer),
	}

	myview = newView
	PrintView(myview)

	for _, apeer := range myview.Members {
		if apeer.Id != myself.Id {
			err := sendMessage(apeer, newViewMessage{reqCount, newView})
			if err != nil {
				logString(err)
			}
		}
	}

	return
}

func pushDelOp(peerId int) {

	newView := view{
		Viewid:  myview.Viewid + 1,
		Leader:  myview.Leader,
		Members: myview.Members,
	}

	for i := 0; i < len(newView.Members); i++ {
		if newView.Members[i].Id == peerId {
			newView.Members = append(newView.Members[:i], newView.Members[i+1:]...)
		}
	}

	myview = newView
	PrintView(myview)

	for _, apeer := range myview.Members {
		if apeer.Id != myself.Id {
			err := sendMessage(apeer, newViewMessage{reqCount, newView})
			if err != nil {
				logString(err)
			}
		}
	}

	return
}

func handleNewView(rw *bufio.ReadWriter) {
	logString("Receive New View data:")
	var newView newViewMessage
	dec := gob.NewDecoder(rw)
	err := dec.Decode(&newView)
	if err != nil {
		logString("Error decoding GOB New View data:", err)
		return
	}

	myview = newView.NewView
	PrintView(myview)
	return
}

func handleNewLeader(rw *bufio.ReadWriter) {

	logString("Receive New Leader data:")
	var message newLeaderMessage
	dec := gob.NewDecoder(rw)
	err := dec.Decode(&message)
	if err != nil {
		logString("Error decoding GOB New Leader data:", err)
		return
	}


	apeer := getPeerById(message.PeerId)

	if apeer.Id != myself.Id{
		myview.Leader = &apeer
		myview.Viewid += 1

		PrintView(myview)
	}

	return
}

func handleHeartBeat(rw *bufio.ReadWriter) {

	var newHeartbeat heartBeatMessage
	dec := gob.NewDecoder(rw)
	err := dec.Decode(&newHeartbeat)
	if err != nil {
		logString("Error decoding GOB HeartBeat data:", err)
		return
	}

	if myself.Id == myview.Leader.Id {
		checkAndAddNewHeartbeat(newHeartbeat.PeerId)
	}

	for i := 0; i < len(heartbeats); i++ {
		if heartbeats[i].Id == newHeartbeat.PeerId {
			heartbeats = append(heartbeats[:i], heartbeats[i+1:]...)
		}
	}

	return
}

func proposeViewChange(id int, op opType) {

	reqCount += 1

	if len(myview.Members) == 1 && myview.Members[0].Id == myview.Leader.Id && op == ADD {
		pushAddOp(id)
	} else if len(myview.Members) == 2 && myview.Members[0].Id == myview.Leader.Id && op == DEL {
		pushDelOp(id)

	} else {

		newReqMessage := reqMessage{
			ReqId:  reqCount,
			ViewId: myview.Viewid,
			Op:     op,
			PeerId: id,
		}

		newOp := operation{
			Op:     op,
			ReqId:  reqCount,
			View:   myview,
			OKs:    []peer{},
			peerId: id,
		}

		pendingOperations = append(pendingOperations, newOp)

		logString("New Request Message:")
		logString(newReqMessage)

		for _, apeer := range myview.Members {
			if apeer.Id != myself.Id {
				err := sendMessage(apeer, newReqMessage)
				if err != nil {
					logString(err)
				}
			}
		}
	}

	return

}

func checkAndAddNewHeartbeat(id int) {

	searchflag := false
	for _, member := range masterList.Members {
		if id == member.Id {
			searchflag = true
		}
	}

	if searchflag {
		for _, member := range myview.Members {
			if id == member.Id {
				searchflag = false
			}
		}

		if searchflag {
			logString("New Heartbeat Detected")
			proposeViewChange(id, ADD)
		}
	}

	return
}

func sendNewLeaderMessage() {

	message := newLeaderMessage{
		PeerId: myself.Id,
	}

	for _, members := range myview.Members {
		sendMessage(members, message)
	}

	myview.Leader = &myself
	myview.Viewid += 1

	PrintView(myview)

}

func sendMessage(apeer peer, message interface{}) error {

	var messageString string

	switch v := message.(type) {
	case okMessage:
		messageString = "OK\n"
		break
	case heartBeatMessage:
		messageString = "HEARTBEAT\n"
		break
	case reqMessage:
		messageString = "REQ\n"
		break
	case newViewMessage:
		messageString = "NEWVIEW\n"
		break
	case newLeaderMessage:
		messageString = "NEWLEADER\n"
		break
	default:
		logString("INVALID MESSAGE TYPE:", v)
		err := errors.New("invalid message type")
		return err
	}



	rw, err := Open(apeer.Ip + apeer.Port)
	if err != nil {
		return err
	}

	enc := gob.NewEncoder(rw)

	n, err := rw.WriteString(messageString)
	if err != nil {
		logString(n)
		return err
	}

	err = enc.Encode(message)
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
	endpoint.AddHandleFunc("REQ", handleReq)
	endpoint.AddHandleFunc("OK", handleOK)
	endpoint.AddHandleFunc("NEWVIEW", handleNewView)
	endpoint.AddHandleFunc("NEWLEADER", handleNewLeader)
	endpoint.AddHandleFunc("HEARTBEAT", handleHeartBeat)

	go heartBeat()
	return endpoint.Listen()
}

func init() {
	log.SetFlags(log.Lshortfile)
	return
}

func main() {
	reqCount = 0

	id := flag.String("id", "", "the process id of this process so it can look itself up.")
	verb := flag.String("v", "", "Set to anything to turn verbose logging on.")
	config := flag.String("config", "", "config file with network data in it. Defaults to network.txt")
	flag.Parse()

	if *id != "" {

		intId, err := strconv.Atoi(*id)
		if err != nil {
			logString(err)
			return
		}
		myself.Id = intId
	} else {
		fmt.Println("You must specify a process Id using the --id flag.  Process quitting.")
		return
	}

	if *verb != "" {
		verbose = true
	}

	if *config != ""{
		readConfig(*config)
	} else {
		readConfig("network.txt")
	}



	for _, member := range masterList.Members {
		if myself.Id == member.Id {
			myself = member
		}
	}

	fmt.Println("Starting process, my stats are: ", myself)

	myview = view{
		Leader:  masterList.Leader,
		Viewid:  0,
		Members: []peer{*masterList.Leader},
	}
	logString("Master list of possible friends:")
	if verbose {
		PrintView(masterList)
	}

	err := server()
	if err != nil {
		logString("Error: ", err)
		return
	}

	logString("Server done.")
	return
}

func heartBeat() error {

	// initial heartbeats
	for {

		timer := time.NewTimer(time.Second)

		<-timer.C

		for _, apeer := range masterList.Members {

			err := sendMessage(apeer, heartBeatMessage{myself.Id})
			if err != nil {
				logString("Initial Heartbeat Error, Probably fine. ", err)

			}
		}

		if len(myview.Members) >= 2{
			break
		}

	}



	// Actual heartbeat loop

	for {
		timer := time.NewTimer(time.Second)

		<-timer.C

		for _, apeer := range myview.Members {

			if apeer.Id != myself.Id {
				err := sendMessage(apeer, heartBeatMessage{myself.Id})
				if err != nil {
					logString("Heartbeat Error", err)

					heartbeats = append(heartbeats, apeer)

				}
			}
		}

		checkForBadHearts()

	}

	return nil
}

func checkForBadHearts() {

	for _, apeer := range myview.Members {

		count := 0
		for _, heart := range heartbeats {
			if heart.Id == apeer.Id {
				count += 1
			}
		}
		if count > allowedBadHearts {
			fmt.Println("Trouble detecting heartbeat from process ", apeer.Id)
			if myself.Id == myview.Leader.Id {
				proposeViewChange(apeer.Id, DEL)
			}

			if apeer.Id == myview.Leader.Id {

				fmt.Println("dead process is the leader, determining new leader")
				lowestProcId := 0
				for _, members := range myview.Members {
					if members.Id != myview.Leader.Id {
						if lowestProcId == 0 {
							lowestProcId = members.Id
						} else if lowestProcId >= members.Id{
							lowestProcId = members.Id
						}
					}



				}

				if lowestProcId == myself.Id {
					fmt.Println("I am the new leader")
					sendNewLeaderMessage()
				}

			}

			for i := 0; i < len(heartbeats); i++ {
				if heartbeats[i].Id == apeer.Id {
					heartbeats = append(heartbeats[:i], heartbeats[i+1:]...)
				}
			}

		}
	}

}

func Open(addr string) (*bufio.ReadWriter, error) {

	logString("Dial " + addr)
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		logString("Dialing " + addr + " failed")
		logString(err)
		return nil, err
	}

	return bufio.NewReadWriter(bufio.NewReader(conn), bufio.NewWriter(conn)), nil

}

func readConfig(config string) {

	csvFile, _ := os.Open(config)
	reader := csv.NewReader(bufio.NewReader(csvFile))
	linecount := 1
	for {
		line, err := reader.Read()
		if err == io.EOF {
			break
		} else if err != nil {
			fmt.Println("Error Reading from file.")
			log.Fatal(err)
		}


		masterList.Members = append(masterList.Members, peer{
			Ip:   line[0],
			Port: line[1],
			Id:   linecount,
		})

		if linecount == 1 {
			masterList.Leader = &peer{
				Ip:   line[0],
				Port: line[1],
				Id:   linecount,
			}
		}

		linecount++
	}

}

func PrintView(aview view) {

	fmt.Println("===============================================================================")

	fmt.Println("View:")
	fmt.Println(aview , "\n")
	fmt.Println("Leader:")
	fmt.Println(aview.Leader)
	fmt.Println("===============================================================================")
	return
}

func getPeerById(peerid int) peer {

	for _, apeer := range masterList.Members {
		if apeer.Id == peerid {
			return apeer
		}
	}

	return peer{"", "", 0}
}

func logString(str ...interface{}) {
	if verbose {
		log.Println(str)
	}
}

/**

    if *connect != ""{
        err := client(*connect)
        if err != nil{
            log.Println("Error:", err)
        }
        log.Println("Client done.")
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

    rw, err:= Open(ip + myself.port)
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
**/
