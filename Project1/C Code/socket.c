#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <string.h>


int openSocket(int port, int type){


    char portstr[5];
    sprintf(portstr, "%d", port);

    struct sockaddr_in sa; // IPv4

    inet_pton(AF_INET, "127.0.0.1", &(sa.sin_addr)); // IPv4

    int status;
    struct addrinfo hints;
    struct addrinfo *res;  // will point to the results

    memset(&hints, 0, sizeof hints); // make sure the struct is empty
    hints.ai_family = sa.sin_addr;     
    hints.ai_socktype = type; 
    hints.ai_flags = AI_PASSIVE;     // fill in my IP for me

    if ((status = getaddrinfo(NULL, portstr, &hints, &res)) != 0) {
        fprintf(stderr, "getaddrinfo error: %s\n", gai_strerror(status));
        exit(1);    
    }

    int s;

    s = socket(res->ai_family, res->ai_socktype, res->ai_protocol);

    printf("socketfd:%d\n", s);

    // servinfo now points to a linked list of 1 or more struct addrinfos

    // ... do everything until you don't need servinfo anymore ....

    freeaddrinfo(res); // free the linked-list


    return 1;
}



int main () {

    
    openSocket(3490, SOCK_DGRAM);

    printf("Program exiting.\n");

    return 0;
}