
import sys
import socket
import csv
import pickle
import random

# command line args: speaker (bool)

# Globals:
myHostName = None
myPort = None
myProcId = None
myIP = None
myNetworkData = []
iAmASpeaker = False
seq = 1
myMessageQueue = []
Delivered = []
MessageCount = 4

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
    listeningSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    listeningSocket.bind((myIP, int(myPort)))
    return listeningSocket

def closeSocket(mySocket):
    mySocket.close()
    return

def broadcast(message):
    global myNetworkData

    for i in myNetworkData:
        sendMessage(message, i['ip'], i['port'])
    
    return

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
    global myMessageQueue
    seq = max(message['msg_id'], seq) + 1

    message['deliverable'] = False
    message['seq'] = seq
    myMessageQueue.append(message)
    ackMessage = conAckMessage(message['sender'], message['msg_id'], seq)
    ip, port = getIPandPortbyProcId(message['sender'])
    if ip and port:
        sendMessage(ackMessage, ip, port)
    else:
        print("ip and port not found, check hostfile")

    return

def proscessAckMessage(message):
    global myMessageQueue
    for i in myMessageQueue:
        if (i['msg_id'] == message['msg_id']):
            i[message['proposer']] = message['proposed_seq']
            #i['msg_id'][message['proposer']] = message['proposed_seq']
    
    return


def proscessSeqMessage(message):
    global myMessageQueue
    global Delivered

    for i in myMessageQueue:
        if i['msg_id'] == message['msg_id']:
            i['seq'] = message['final_seq']
            Delivered.append(i)
            Delivered = sorted(Delivered, key=lambda i: i['seq']) 

    return

def SpeakerBehavior():
    global myMessageQueue
    global Delivered
    global MessageCount

    unAckdMessage = False

    print(str(myMessageQueue))

    # check to see if we have unacknowledged messages we need to ask about.
    for i in myMessageQueue:
        if i['deliverable'] == False:
            deliverableCheck = True
            for j in myNetworkData:
                if not j['processid'] in i.keys():
                    deliverableCheck = False
                    ip, port = getIPandPortbyProcId(j['processid'])
                    sendMessage(conDataMessage(i['seq'], i['data']),ip,port)
                    unAckdMessage = True
                    break
            if deliverableCheck:
                i['deliverable'] = True
                i['seq'] = getMaxSeq(i)
                broadcast(conSeqMessage(i['sender'],i['msg_id'],i['seq']))


    if MessageCount >= 0 and not unAckdMessage:
        broadcast(conDataMessage(seq +1, random.randint(1,50)))
        MessageCount -= 1
    if MessageCount <= 0:
        broadcast(conTerMessage())

    return


def getMaxSeq(message):
    temp = []
    for i in range(len(myNetworkData)):
        if i in message.keys():
            temp.append(message[i])

    if len(temp) > 0:
        return max(temp)

    return 0
    


def listenerBehavior():
    mysocket = openListeningPort()

    done = False

    global seq
    global myMessageQueue

    while not done:

        if iAmASpeaker:
            SpeakerBehavior()

        temp = mysocket.recv(4096)

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
                done = True


            temp = None
            
    closeSocket(mysocket)
    return



def main():
    setUp()

    if iAmASpeaker:
        print("I am a sender")
    else:
        print("I am a reciever")
    
    listenerBehavior()
    print(str(Delivered))
    return


main()
