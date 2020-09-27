import socket
from threading import Thread
import random
import sys
from time import sleep
from scapy.all import *
import csv



#keep all listener endpoints alive that one of which will receive a connection from the other end(puncher)
def keep_listeners_alive(remote_ip, random_remote_ports, packets_per_port_per_min):
    global connection_established
    global listener_sockets

    while True: #loop to check if any listener sockets exist
        if listener_sockets:
            break

    packets_per_sec = (len(listener_sockets) * packets_per_port_per_min)/60
    sleep_time =float('%.6f'%(1/packets_per_sec))
    for listener in listener_sockets: #loop to keep all existing listener sockets/endpoints on router alive 
        if not connection_established:
            remote_address = (remote_ip, random_remote_ports[listener_sockets.index(listener)] )
            message = remote_ip + " " + str(random_remote_ports[listener_sockets.index(listener)])
            listener.sendto(message.encode(), remote_address)
            sleep(sleep_time)
        else:
            break



#listen on all listener socket for an incoming message from the other end(puncher)
def listener_sockets_recv():
    global public_ports
    global connection_established
    global listener_sockets
    print("listening for a connection...")
    while True:
        for listener_socket in listener_sockets:
            try:
                listener_socket.settimeout(0.00)
                data, server = listener_socket.recvfrom(1024)
                if server: #if a message is received send a message back
                    message = str(server[0]) + " " + str(server[1])
                    listener_socket.sendto(message.encode(), server)
                    connection_established = True #set True to stop receiving on all sockets
                    public_address = (public_ip, public_ports[listener_sockets.index(listener_socket)])
                    print("\nconnection received, local address:",listener_socket.getsockname(),
                        "\nlocal public endpoint: ",public_address,
                        "\nremote endpoint ",server)
                    print("\nclosing all other listener sockets")
                    for i in range(len(listener_sockets)): #close all other listener sockets
                        if listener_sockets[i] != listener_socket:
                            listener_sockets[i].close()
                    return listener_socket,server #return the winning socket as a mean of connection with the remote address
            except:
                pass



"""
open a number (len(lookup_sockets)) of Network Address Translation(NAT) entries and keep them alive on the local router 
for the same remote port, by sending a packet periodically to rhost:rport on each socket 
"""
def keep_lookup_socks_alive(lookup_sockets,remote_ip,remote_port,packets_per_port_per_min):
    global next_pport_lookup
    print("keeping port ", remote_port , " lookup sockets alive...")
    packets_per_sec = (len(lookup_sockets) * packets_per_port_per_min)/60
    sleep_time =float('%.6f'%(1/packets_per_sec))
    keep_alive = True
    while keep_alive:
        for i in range(len(lookup_sockets)):
            if not next_pport_lookup: #keep looping until a public port connected to current remote port is found
                remote_address = (remote_ip,remote_port)
                message = remote_ip + str(remote_port)
                lookup_sockets[i].sendto(message.encode(), remote_address)
                sleep(sleep_time)
            else:
                keep_alive = False
                break
    print("keeping lookup sockets alive stopped.")



"""
#on multupile sockets listen for an incoming (crafted) packets,
connection will be established when one of the packets has:
source ip = remote ip(puncher) , source port = randomly chosen(known) remote port
destination ip = local router ip , destination port = randomly assigned by router(unknown) public port
"""
def lookup_socks_recv(lookup_sockets):
    global listener_sockets
    global public_ports
    global next_pport_lookup
    keep_receiving = True
    print("receiving on all socks...")
    while keep_receiving:
        for i in range(len(lookup_sockets)):
            try:
                lookup_sockets[i].settimeout(0.00)
                data, server = lookup_sockets[i].recvfrom(1024)
                if server: #if a packet is received then a randomly chosen public port was correct
                    message = str(server[0]) + " " + str(server[1])
                    public_ports.append(int(data.decode())) #add it to the discovered public ports
                    local_address = lookup_sockets[i].getsockname() #get address of local socket
                    next_pport_lookup = True #to stop keep_lookup_socks_alive and punch_ports
                    keep_receiving = False # to stop lookup_socks_recv
                    print("public_port ", public_ports[-1], "is connected to remote port ",remote_port)
                    print("closing lookup sockets for ",remote_port)
                    for i in range(len(lookup_sockets)): #close all lookup sockets
                        lookup_sockets[i].close()
                    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    listener_sockets.append(listener_socket)  #add a listener socket with the address was used by closed socket an bind it
                    listener_sockets[-1].bind(local_address)  #to start listening on it and keeping it alive
                    print("lookup socket has been added to listener sockets list.")

                    break
            except:
                pass
    print("receiving on all lookup sockets stopped.")



"""
send crafted packets with:
source ip = remote ip(puncher) , source port = randomly chosen(known) remote port
destination ip = public ip = local router ip , destination ports = randomly chosen public ports
"""
def punch_ports(public_ip, remote_ip, remote_port,num_of_lookup_connections):
    global next_pport_lookup
    global public_ports

    print("punching for ",remote_port)
    keep_punching = True

    while keep_punching:

        num_random_public_ports = int(65536/num_of_lookup_connections)*2 # for 1000 lookup connections try 131 ports each loop
        random_public_ports = random.sample(range(1,65536), num_random_public_ports )

        for public_port in random_public_ports:
            if not next_pport_lookup: #wait to receive something and discover a public port
                payload = str(public_port)
                spoofed_packet = IP(src=remote_ip, dst=public_ip) / UDP(sport=int(remote_port), dport=int(public_port)) / payload 
                send(spoofed_packet, verbose=0)
                sleep(0.001)
            else:
                keep_punching = False
                break
    
    print("punching for ",remote_port, "stopped.")



"""
initialize a list of UDP sockets that each loop all will listen for one of the remote ports
to facilitate the lookup of 1 public port that connects with it
"""
def find_public_port(local_ip, public_ip, remote_ip, remote_port):
    num_of_lookup_connections = 1000 #number of endpoints to be created on router each time to discover a public port
    lookup_sockets = []

    for i in range(num_of_lookup_connections): #initilize lookup sockets list
        lookup_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lookup_sockets.append(lookup_socket)

    for i in range(num_of_lookup_connections): #bind lookup sockets
        lookup_sockets[i].bind((local_ip, 0))


    #start thread to keep lookup sockets alive while punching/searching
    packets_per_port_per_min = 10
    thread_keep_lookup = Thread(target = keep_lookup_socks_alive,args=(lookup_sockets,remote_ip,remote_port,packets_per_port_per_min,))
    thread_keep_lookup.daemon = True
    thread_keep_lookup.start()

    #start thread to receive from lookup sockets while punching/searching
    thread_lookup_recv = Thread(target = lookup_socks_recv,args=(lookup_sockets,))
    thread_lookup_recv.daemon = True
    thread_lookup_recv.start()

    #start punching/searching thread
    thread_punch_ports = Thread(target = punch_ports,args=(public_ip, remote_ip, remote_port,num_of_lookup_connections,))
    thread_punch_ports.daemon = True
    thread_punch_ports.start()

    thread_punch_ports.join() #wait until punching is over and a public port is found



###################################################################################################################################################
if len(sys.argv) < 6:
    print("Usage: listener.py <local private ip> <local public ip> <remote public ip> <remote public port range> <number of ports to open>")
    print("example: listener.py 10.0.0.5 1.1.1.1 2.2.2.2 35000-65000 64")
    sys.exit()



local_ip = sys.argv[1]
public_ip = sys.argv[2]
remote_ip  = sys.argv[3]
ports_range = range(int(sys.argv[4].split("-")[0]),int(sys.argv[4].split("-")[1]))
total_listeners = int(sys.argv[5])



global public_ports #public ports connected to remote ports to be discovered
public_ports = []
global listener_sockets #sockets which are listening on a known remote port and known/discovered public ports 
listener_sockets = []
global connection_established #signals keep_listeners_alive and listener_sockets_recv to stop
connection_established = False 
global next_pport_lookup #signals keep_lookup_socks_alive and lookup_socks_recv to stop once a pport is found
random_remote_ports = random.sample(ports_range, total_listeners) #range of remote ports anticipated to be used by remote host when port-overloaded



#start listening to listener sockets and keep alive once the list gets populated
packets_per_port_per_min = 15
thread_keep_listeners = Thread(target = keep_listeners_alive,args=(remote_ip, random_remote_ports, packets_per_port_per_min,))
thread_keep_listeners.daemon = True
thread_keep_listeners.start()



#find a public port for each remote port - same remote ip same source ip(router)
for remote_port in random_remote_ports:
    next_pport_lookup = False
    find_public_port(local_ip, public_ip, remote_ip, remote_port)



print("remote ports",random_remote_ports)
print("public_ports",public_ports)



with open("public_ports.csv", "w") as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(public_ports)
print("please provide public_ports.csv file to the puncher to continue the process from the other end.")



suggestion = int((65535/total_listeners)*2)
print("recomended number of puncher sockets: ",suggestion)



connected_socket,server = listener_sockets_recv()
print("keeping connection alive: ",connected_socket.getsockname())
while True:
    message = "keep_alive"
    connected_socket.sendto(message.encode(), server)
    sleep(5)

###################################################################################################################################################
#from here the user can add the code desired to use the connection, or close this program and under 30-60 sec use the 
#same local ip:local port on other program before the connection times out on the router, with 'keep alive' periodic packets sent.
#note: this may not work if the the public ip is not the next hop from the local gateway 
#Author: Azeer Esmail