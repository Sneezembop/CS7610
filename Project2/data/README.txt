CS 7610 Project 2 README
Miles Benjamin

How to make prj2:
    Run the make file included with the project.  Golang must be installed on the machine.
    Alternatively run "go build prj2.go"

How to run prj2:
    Run from the command line on up to as many machines as you specify in the hostfile file
    Always start with the process that is the leader.

    I have found that running the program manually on multiple terminals gives the clearest and most compelling demo.
    Therefore here are instructions on how to manually execute the test cases in the spec:

    TESTCASE 1:
        run ./prj2 -id 1 on the leader machine, wait for it to print out it's stats
        run ./prj2 -id 2 on the next machine, wait for a new view to print on both machines.
        keep running machines in this manner until you're satisfied.

    TESTCASE 2:
        Repeat TESTCASE 1
        Press CTRL + C on one of the non-leader machines to crash the process
        Watch each process print the line "Trouble detecting heartbeat from process XXX"

    TESTCASE 3:
        Repeat TESTCASE 2
        Watch after each process has printed "Trouble detecting heartbeat from process  XXX"
        Watch a new view print on each machine which does not contain the crashed process

    TESTCASE 4:
        Repeat TESTCASE 1
        Press CTRL + C on a non-leader process
        Quickly press CTRL + C on the leader process
        Watch each process print the line "Trouble detecting heartbeat from process  XXX" where XXX is the leader
        One process will print "I am the new leader"
        A new view will print on each machine where the leader has updated
        A new view will print on each machine where the crashed processes are no longer present.


Command Line Flags:

    -id XXX - * REQUIRED * The ID of the process, which must match the hostfile.
    -config XXX - hostfile can be specified, otherwise it will default to 'network.txt'
    -v XXX - Verbose logging to the console. Can be enabled on multiple machines.  The argument doesn't do anything.
    
Formatting network.txt:
    Network.txt is a CSV file and contains only the network data for each machine in the network.
    Here's an example with 5 machines in the network formatted for easy reading.

        ip,             port        
        10.168.33.10,   :5501
        10.168.33.20,   :5502
        10.168.33.30,   :5503
        10.168.33.40,   :5504
        10.168.33.50,   :5505

    You must specify a unique ip address & port combination for each member of the network. 
    (The IP addresses can be the same as long as the ports are different and vice-versa)
    The Leader process is always the one on the first line. (at least to start).

Known issues:
    I haven't been able to get a 4th machine to join the network.  I'm not sure if this is a failing on my local machine 
    or (more likely) an error in my code.  If a 4th machine starts running and an existing machine crashes.
    The 4th machine will proceed in joining.

    Cascading joins (two machines that start in rapid successsion) should work.  
    Cascading failures (two machines that fail in rapid succession) may fail, unless the second machine to fail is the leader
    