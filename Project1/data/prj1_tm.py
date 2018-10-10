
import sys
import socket
import csv
import pickle
import random
import pprint as pp

# command line args: -p port, -t test, -s snapshot, -l logging, -h hostfile

# Globals:
myPort = None
myProcId = None
myIP = None
myNetworkData = []
iAmASpeaker = False
seq = 1
myDataMessageQueue = []
Delivered = []
MessageCount = 5
totalSpeakers = 0
outgoingMessageQueue = []
snapshotBuffer = ""
simulatePacketLoss = False
snapshotCount = -1
loggingEnabled = False
hostfile = 'network.txt'


def setUp():
    global myNetworkData
    global myPort
    global myProcId
    global myIP
    global iAmASpeaker
    global totalSpeakers
    global simulatePacketLoss
    global snapshotCount
    global loggingEnabled
    global hostfile

    if (len(sys.argv) > 1):
        # print(str(sys.argv))
        for i in range(len(sys.argv)):
            if sys.argv[i] == "-p":
                try:
                    myPort = sys.argv[i + 1]
                except Exception as msg:
                    print(msg)
                    print("port not specified")
                    return
            if sys.argv[i] == "-t":
                simulatePacketLoss = True
            if sys.argv[i] == "-s":
                try:
                    snapshotCount = int(sys.argv[i + 1])
                except Exception as msg:
                    print(msg)
                    print("snapshot count not specified, snapshot disabled")
            if sys.argv[i] == "-l":
                loggingEnabled = True
            if sys.argv[i] == "-h":
                try:
                    hostfile = int(sys.argv[i + 1])
                    open(hostfile, mode='r')
                except Exception as msg:
                    print(msg)
                    print("hostfile not specified")
                    myPort = None
                    return

    with open(hostfile, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        temp = None
        for row in csv_reader:

            temp = {'port': row['port'], 'ip': row['ip'],
                    'processid': row['processid'], 'speaker': row['speaker']}
            myNetworkData.append(temp)

    # print('MyNetworkData:')
    # print(str(myNetworkData))

    for i in myNetworkData:
        if (i['port'] == str(myPort)):
            myProcId = i['processid']
            myIP = i['ip']
            if (i['speaker'] == "1"):
                iAmASpeaker = True
        if (i['speaker'] == "1"):
            totalSpeakers = totalSpeakers + 1

    if (myIP == None):
        print("invalid port specified, check the network.txt file")

    return


def openListeningPort():
    mysocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    mysocket.bind((myIP, int(myPort)))
    return mysocket


def closeSocket(mySocket):
    mySocket.close()
    return


def broadcast(message):
    global myNetworkData
    global outgoingMessageQueue

    outgoingMessageQueue.append((message, myIP, myPort))

    for i in myNetworkData:
        if i['port'] != myPort:
            outgoingMessageQueue.append((message, i['ip'], i['port']))

    return


def newMessageId():
    global seq
    global myDataMessageQueue

    temp = seq

    for i in myDataMessageQueue:
        temp = max(temp, i['msg_id'])

    temp = temp + int(myProcId)
    return temp


def sendMessage(message, ip, port):
    tempsocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    addr = (ip, int(port))
    tempsocket.sendto(message, addr)

    closeSocket(tempsocket)
    return


def getIPandPortbyProcId(procId):
    global myNetworkData

    ip = None
    port = None

    for i in myNetworkData:
        if (i['processid'] == procId):
            ip = i['ip']
            port = i['port']

    return ip, port


def conDataMessage(msg_id, data):
    global myProcId
    message = {'type': 1, 'sender': myProcId, 'msg_id': msg_id, 'data': data}
    pickMessage = pickle.dumps(message)
    return pickMessage


def conAckMessage(sender, msg_id, proposed_seq):
    global myProcId
    message = {'type': 2, 'sender': sender, 'proposer': myProcId,
               'msg_id': msg_id, 'proposed_seq': proposed_seq}
    pickMessage = pickle.dumps(message)
    return pickMessage


def conSeqMessage(sender, msg_id, final_seq):
    global myProcId
    message = {'type': 3, 'sender': sender, 'final_proposer': myProcId,
               'msg_id': msg_id, 'final_seq': final_seq}
    pickMessage = pickle.dumps(message)
    return pickMessage


def conSnapshotReqMessage():
    global myProcId
    message = {'type': 5, 'sender': myProcId}
    pickMessage = pickle.dumps(message)
    return pickMessage


def conSnapshotDataMessage():
    message = {'type': 6, 'sender': myProcId}
    message['myStats'] = {'IP': myIP, 'Port': myPort, 'Speaker': iAmASpeaker}
    message['incommingQueue'] = myDataMessageQueue
    message['outgoingQueue'] = outgoingMessageQueue
    message['delivered'] = Delivered

    pickMessage = pickle.dumps(message)
    return pickMessage


def unpackMessage(message):
    return pickle.loads(message)


def proscessDataMessage(message):
    global seq
    global myDataMessageQueue
    global outgoingMessageQueue

    tempSeq = 0

    alreadyHaveMessage = False

    for i in myDataMessageQueue:
        if i['msg_id'] == message['msg_id']:
            alreadyHaveMessage = True
            tempSeq = i['seq']

    for i in Delivered:
        if i['msg_id'] == message['msg_id']:
            alreadyHaveMessage = True

    if not alreadyHaveMessage:
        seq = max(message['msg_id'], seq) + 1
        message['deliverable'] = False
        message['seq'] = seq
        tempSeq = seq
        myDataMessageQueue.append(message)

    ackMessage = conAckMessage(message['sender'], message['msg_id'], tempSeq)
    ip, port = getIPandPortbyProcId(message['sender'])
    if ip and port:
        outgoingMessageQueue.append((ackMessage, ip, port))
    else:
        print("ip and port not found, check hostfile")

    return


def proscessAckMessage(message):
    global myDataMessageQueue

    foundMessage = False
    for i in myDataMessageQueue:
        if (i['msg_id'] == message['msg_id']):
            foundMessage = True
            tup = (message['proposer'], message['proposed_seq'])
            if 'proposed_seqs' not in i.keys():
                i['proposed_seqs'] = []

            alreadyAckd = False

            for j in i['proposed_seqs']:
                if j[0] == message['proposer']:
                    alreadyAckd = True

            if not alreadyAckd:
                i['proposed_seqs'].append(tup)

        if iAmASpeaker and i['sender'] == myProcId:
            if 'proposed_seqs' in i.keys() and len(i['proposed_seqs']) == len(myNetworkData):
                i['deliverable'] = True
                i['seq'] = getMaxSeq(i)
                broadcast(conSeqMessage(i['sender'], i['msg_id'], i['seq']))

    if not foundMessage:
        for i in Delivered:
            if i['msg_id'] == message['msg_id']:
                foundMessage = True
                if iAmASpeaker and i['sender'] == myProcId:
                    broadcast(conSeqMessage(
                        i['sender'], i['msg_id'], i['seq']))

    # if not foundMessage:
    #    if iAmASpeaker:
    #        broadcast(conDataMessage(message['msg_id'],message['data']))

    return


def proscessSeqMessage(message):
    global myDataMessageQueue
    global Delivered

    for i in myDataMessageQueue:
        if i['msg_id'] == message['msg_id']:
            i['seq'] = message['final_seq']
            i['deliverable'] = True
            Delivered.append(i)
            myDataMessageQueue.remove(i)
            processString = str(myProcId) + ": Processed message " + str(message['msg_id']) + " from sender " + str(
                message['sender']) + " with seq (" + str(message['final_seq']) + ", " + str(message['final_proposer']) + ")"
            pp.pprint(processString)
            log(myDataMessageQueue, "MyDataMessageQueue: ")

    return


def proscessSnapShotReq(message):

    snapShotDatamessage = conSnapshotDataMessage()
    ip, port = getIPandPortbyProcId(message['sender'])
    if ip and port:
        outgoingMessageQueue.append((snapShotDatamessage, ip, port))
    else:
        print("ip and port not found, check hostfile")

    return


def processSnapShotData(message):
    global snapshotBuffer

    mystring = pp.pformat(message)

    snapshotBuffer = snapshotBuffer + mystring + "\n"

    return


def SpeakerBehavior():
    global myDataMessageQueue
    global MessageCount
    global snapshotCount
    global seq

    unAckdMessage = False

    # check to see if we have messages we can deliver.
    for i in myDataMessageQueue:
        if i['deliverable'] == False:
            # print(i)
            if 'proposed_seqs' in i.keys() and len(i['proposed_seqs']) == len(myNetworkData):
                i['deliverable'] = True
                i['seq'] = getMaxSeq(i)
                broadcast(conSeqMessage(i['sender'], i['msg_id'], i['seq']))
            elif i['sender'] == myProcId:
                unAckdMessage = True
                log(i, "Message missing acknowledgements:")

    if MessageCount > 0 and not unAckdMessage:
        seq = seq + 1
        broadcast(conDataMessage(newMessageId(), random.randint(1, 50)))
        MessageCount = MessageCount - 1
        snapshotCount = snapshotCount - 1
    elif (unAckdMessage):
        checkForUnackdMessages()

    if (snapshotCount == 0):
        broadcast(conSnapshotReqMessage())
        snapshotCount = -1

    return


def checkForUnackdMessages():
    for i in myDataMessageQueue:
        if i['deliverable'] == False:
            if 'proposed_seqs' in i.keys() and len(i['proposed_seqs']) != len(myNetworkData):
                procIds = []
                for j in myNetworkData:
                    procIds.append(j['processid'])
                for j in i['proposed_seqs']:
                    procIds.remove(j[0])

                for j in procIds:
                    tempMessage = conDataMessage(i['msg_id'], i['data'])
                    ip, port = getIPandPortbyProcId(j)
                    outgoingMessageQueue.append((tempMessage, ip, port))
    return


def reAckmessages():
    global myDataMessageQueue

    myDataMessageQueue.sort(reverse=random.randint(0, 1) == 1)

    for i in myDataMessageQueue:
        if i['deliverable'] == False:
            log(i, "Found this message in queue, reacking: ")
            ackMessage = conAckMessage(i['sender'], i['msg_id'], i['seq'])
            log(unpackMessage(ackMessage), "New Ack Message:")
            ip, port = getIPandPortbyProcId(i['sender'])
            if ip and port:
                outgoingMessageQueue.append((ackMessage, ip, port))
                return
            else:
                print("ip and port not found, check hostfile")

    return


def processOutgoingMessage(outgoingQueue):

    messageData = outgoingQueue.pop(0)
    message = messageData[0]
    ip = messageData[1]
    port = messageData[2]

    temp = unpackMessage(message)

    if simulatePacketLoss:
        if (random.randint(0, 10) >= 8):
            log(temp, "Packet Lost:")
            return

    log(temp, "Message Sent:")
    sendMessage(message, ip, port)

    return


def getMaxSeq(message):
    temp = []
    for i in message['proposed_seqs']:
        temp.append(i[1])

    if len(temp) > 0:
        return max(temp)

    return 0


def listen(mysocket):

    try:
        temp = mysocket.recv(4096)
    except socket.error:
        temp = []
        return True

    if len(temp) > 0:
        temp = unpackMessage(temp)
        log(temp, "Message Recieved:")

        # Message type 4 is deprecated
        if temp['type'] == 1:
            proscessDataMessage(temp)
        elif temp['type'] == 2:
            proscessAckMessage(temp)
        elif temp['type'] == 3:
            proscessSeqMessage(temp)
        elif temp['type'] == 5:
            proscessSnapShotReq(temp)
        elif temp['type'] == 6:
            processSnapShotData(temp)
    return False


def main():
    setUp()

    if myIP == None:
        return

    if iAmASpeaker:
        print("I am a sender")
    else:
        print("I am a reciever")

    done = False

    global seq
    global myDataMessageQueue
    global outgoingMessageQueue
    global Delivered

    finalMessageCount = MessageCount * totalSpeakers

    mysocket = openListeningPort()
    mysocket.settimeout(5)

    while not done:

        timeout = listen(mysocket)
        mysocket.settimeout(0.5)

        while len(outgoingMessageQueue) > 0:
            processOutgoingMessage(outgoingMessageQueue)

        if timeout:
            if iAmASpeaker:
                SpeakerBehavior()

            if len(myDataMessageQueue) > 0 and random.randint(0, 10) > 5:
                reAckmessages()

        done = (len(Delivered) == finalMessageCount and (
            len(outgoingMessageQueue) == 0) and timeout)

    closeSocket(mysocket)

    printOutput(Delivered)

    if snapshotBuffer != "":
        print("printing snapshot data:")
        print(snapshotBuffer)

    return


def printGlobals():
    global myNetworkData
    global myPort
    global myProcId
    global myIP
    global iAmASpeaker

    print("myPort: " + str(myPort))
    print("myProcId: " + str(myProcId))
    print("myIP: " + str(myIP))
    print("iAmASpeaker: " + str(iAmASpeaker))
    print("myNetworkData: " + str(myNetworkData))
    return


def printOutput(deliveredList):
    deliveredList = sorted(deliveredList, key=lambda i: i['seq'])

    if loggingEnabled:
        pp.pprint(deliveredList)

    output = ""
    for i in deliveredList:
        output += "id: " + str(i['msg_id']) + " seq: " + str(i['seq']) + ",\n"

    print("Final Sequence:\n" + output)
    return


def log(message, statusmessage):

    if loggingEnabled:
        print(statusmessage)
        pp.pprint(message)
    return


main()
