CS 7610 Project 1 README
Miles Benjamin

How to run prj1_tm.py:
    Run from the command line on as many machines as you specify in the hostfile file
    Recievers will wait indefinitely until they recieve a message
    Senders have a 5 second timeout before they start sending messages

    If you want multiple senders (multicasters), both must be up and running before one reaches it's 5 second timeout
    (I know it's not perfect, I recommend having all machines sitting with commands all written and ready to execute before starting
    any of the machines.)

Command Line Args:

    -p XXX - * REQUIRED * Port number must match a port specified in the hostfile 
    -h XXX - hostfile can be specified, otherwise it will default to 'network.txt'
    -s XXX - Enable snapshot and trigger after XXX messages are sent.  Only Senders may trigger a snapshot.
    -t - Enable 20 % message loss on send for this instance.  Can be enabled on multiple machines.
    -l  - Verbose logging to the console. Can be enabled on multiple machines.
    
Formatting network.txt:
    Network.txt is a CSV file and contains category names in it's first line, followed by values for each machine in the network.
    Here's an example with 5 machines in the network and 2 speakers (multicasters) formatted for easy reading.

        ip,             port,   processid,  speaker
        10.168.33.10,   5501,   1,          1
        10.168.33.20,   5502,   2,          1
        10.168.33.30,   5503,   3,          0
        10.168.33.40,   5504,   4,          0
        10.168.33.50,   5505,   5,          0

    You must specify unique ip addresses, ports, and processids for each member of the network.
    Speaker is either 1 or 0 depending on whether that machine should multicast.  Each instance of the program
    will look up it's own processid and speaker status based on the port number given as a cmd argument.

Known issues:
    There is no way to check for missed messages of some varieties.  
    It is possible that snapshot and final sequence messages are never recovered (Despite my best efforts)
    It's not recommended to run the snapshot portion of the program with packet loss enabled.

    In order to prevent early messages from having the same ID, each sender adds it's process ID to the message id, thus incrementing the sequence count,
    this is why the sequence count seems to jump instead of always incrementing by 1.
    