
import sys
import socket
import csv
import pickle
import random
import pprint as pp

# command line args: speaker (bool)

# Globals:
myHostName = None
myPort = None
myProcId = None
myIP = None
myNetworkData = []
iAmASpeaker = False
seq = 1
myDataMessageQueue = []
Delivered = []
MessageCount = 5
outgoingMessageQueue = []

def setUp():
    global myHostName
    global myNetworkData
    global myPort
    global myProcId
    global myIP
    global iAmASpeaker

    if (len(sys.argv) > 1):
        #print(str(sys.argv))
        if (sys.argv[1] == '1'):
            iAmASpeaker = True



    myHostName = socket.gethostname()
    with open('network.txt', mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        temp = None
        for row in csv_reader:
            
            temp = {'hostname': row['hostname'], 'port': row['port'], 'ip': row['ip'], 'processid': row['processid']}
            myNetworkData.append(temp)


    #print('MyNetworkData:')
    #print(str(myNetworkData))

    for i in myNetworkData:
        if (i['hostname'] == str(myHostName)):
            myPort = i['port']
            myProcId = i['processid']
            myIP = i['ip']


    return

def printGlobals():
    global myHostName
    global myNetworkData
    global myPort
    global myProcId
    global myIP
    global iAmASpeaker


    print("MyHostName: " + str(myHostName))
    print("myPort: " + str(myPort))
    print("myProcId: " + str(myProcId))
    print("myIP: " + str(myIP))
    print("iAmASpeaker: " + str(iAmASpeaker))
    print("myNetworkData: " + str(myNetworkData))
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

    temp = temp + random.randint(1,10)
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

def conDataMessage(msg_id,data):
    global myProcId
    message = {'type': 1, 'sender': myProcId, 'msg_id': msg_id, 'data': data}
    pickMessage = pickle.dumps(message)
    return pickMessage

def conAckMessage(sender,msg_id,proposed_seq):
    global myProcId
    message = {'type': 2, 'sender': sender, 'proposer': myProcId,  'msg_id': msg_id, 'proposed_seq': proposed_seq}
    pickMessage = pickle.dumps(message)
    return pickMessage

def conSeqMessage(sender,msg_id,final_seq):
    global myProcId
    message = {'type': 3, 'sender': sender, 'final_proposer': myProcId,  'msg_id': msg_id, 'final_seq': final_seq}
    pickMessage = pickle.dumps(message)
    return pickMessage

def conTerMessage():
    #termination message for processes to quit
    message = {'type': 4}
    pickMessage = pickle.dumps(message)
    return pickMessage

def unpackMessage(message):
    return pickle.loads(message)

def proscessDataMessage(message):
    global seq
    global myDataMessageQueue
    global outgoingMessageQueue

    seq = max(message['msg_id'], seq) + 1

    message['deliverable'] = False
    message['seq'] = seq
    myDataMessageQueue.append(message)
    ackMessage = conAckMessage(message['sender'], message['msg_id'], seq)
    ip, port = getIPandPortbyProcId(message['sender'])
    if ip and port:
        outgoingMessageQueue.append((ackMessage, ip, port))
    else:
        print("ip and port not found, check hostfile")

    return

def proscessAckMessage(message):
    global myDataMessageQueue
    for i in myDataMessageQueue:
        if (i['msg_id'] == message['msg_id']):
            tup = (message['proposer'], message['proposed_seq'])
            if 'proposed_seqs' not in i.keys():
                i['proposed_seqs'] = []
            i['proposed_seqs'].append(tup)
    
    return


def proscessSeqMessage(message):
    global myDataMessageQueue
    global Delivered

    for i in myDataMessageQueue:
        if i['msg_id'] == message['msg_id']:
            i['seq'] = message['final_seq']
            i['deliverable'] = True
            Delivered.append(i)

    return
 
def SpeakerBehavior():
    global myDataMessageQueue
    global MessageCount
    global seq

    unAckdMessage = False

    # check to see if we have messages we can deliver.
    for i in myDataMessageQueue:
        if i['deliverable'] == False:
            print(i)
            if 'proposed_seqs' in i.keys() and len(i['proposed_seqs']) == len(myNetworkData):
                i['deliverable'] = True
                i['seq'] = getMaxSeq(i)
                broadcast(conSeqMessage(i['sender'],i['msg_id'],i['seq']))
            else:
                unAckdMessage = True


    if MessageCount > 0 and not unAckdMessage:
        seq = seq + 1
        broadcast(conDataMessage(newMessageId(), random.randint(1,50)))
        MessageCount  = MessageCount - 1
        print("broadcasting message count" + str(MessageCount))
    elif (MessageCount == 0):
       # broadcastTermination()
        MessageCount  = MessageCount - 1



    return

def broadcastTermination():
    global myNetworkData
    global outgoingMessageQueue

    message = conTerMessage()

    for i in myNetworkData:
        if i['port'] != myPort:
            outgoingMessageQueue.append((message, i['ip'], i['port']))
    
    outgoingMessageQueue.append((message, myIP, myPort))
        
    return


def processOutgoingMessage(outgoingQueue):

    messageData = outgoingQueue.pop(0)
    message = messageData[0]
    ip = messageData[1]
    port = messageData[2]

    temp = unpackMessage(message)
    print("sending message: " + str(temp) + " to port " + str(port))

    sendMessage(message,ip, port)

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
    except socket.error as msg:
        temp = []


    if len(temp) > 0:
        temp = unpackMessage(temp)
        print(temp)

        if temp['type'] == 1:        
            proscessDataMessage(temp)
        elif temp['type'] == 2:
            proscessAckMessage(temp)
        elif temp['type'] == 3:     
            proscessSeqMessage(temp)
        elif temp['type'] == 4:
            return True
    return False


def main():
    setUp()

    if iAmASpeaker:
        print("I am a sender")
    else:
        print("I am a reciever")

    done = False

    global seq
    global myDataMessageQueue
    global outgoingMessageQueue
    global Delivered

    mysocket = openListeningPort()
    mysocket.settimeout(5)

    while not done:

        listen(mysocket)
        mysocket.settimeout(0.5)

        if len(outgoingMessageQueue) > 0:
            processOutgoingMessage(outgoingMessageQueue)
        else:
            if iAmASpeaker: 
                SpeakerBehavior()

        done = (len(Delivered) == 10 and (len(outgoingMessageQueue) == 0))
    
    closeSocket(mysocket)
    
    printOutput(Delivered)

    return


def printOutput(deliveredList):
    deliveredList = sorted(deliveredList, key=lambda i: i['seq'])

    pp.pprint(deliveredList)
    output = ""
    for i in deliveredList:
        output += str(i['seq']) + ", "

    pp.pprint("Final Sequence: " + output)


main()
