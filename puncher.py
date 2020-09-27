import socket
from threading import Thread
import sys
from time import sleep
import csv



#listen to a reply from listener every time a remote public port is tested 
def recv_punchers(puncher_sockets):
	global stop_thread
	global connection_socket
	global remote_host

	stop_thread = False
	server = None

	while not stop_thread: #keep receivingfrom all sockets until stop signal received
		for i in range(len(puncher_sockets)):

			if not stop_thread: #check stop signal before each recv

				try:
					puncher_sockets[i].settimeout(0.00)
					data, server = puncher_sockets[i].recvfrom(1024)
					if server: #if a message is received
						message = str(server[0]) + " " + str(server[1])
						puncher_sockets[i].sendto(message.encode(), server)
						print("\nconnection received, local address:",puncher_sockets[i].getsockname() ,"\nlocal public endpoint: ",data.decode(),"\nremote endpoint ",server)
						connection_socket = puncher_sockets[i] #save the socket with the connection
						remote_host = server #and the remote address
						for i in range(total_socks): #close all other sockets
							if connection_socket != puncher_sockets[i]:
								puncher_sockets[i].close()
				except:
					pass
			
			else:
				break

	#if stop signal received but no connection: close all sockets
	if not connection_socket:
		for i in range(len(puncher_sockets)): 
			puncher_sockets[i].close()



#try to make a connection through a remote public port provided by the listener side
def punch_port(total_socks,local_ip,remote_ip,remote_port,packets_per_port_per_min):
	global stop_thread
	global connection_socket

	packets_per_sec = (total_socks * packets_per_port_per_min)/60
	sleep_time =float('%.6f'%(1/packets_per_sec))

	remote_address = (remote_ip,  remote_port)
	message = remote_ip + " " +str(remote_port)


	#initilize a total_socks number of sockets to create endpoints on local router that will test a remote public port
	puncher_sockets = []
	print("binding sockets..")
	for i in range(total_socks):
		puncher_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		puncher_sockets.append(puncher_socket)
		puncher_sockets[i].bind((local_ip, 0))


	#start a thread to receive on puncher sockets a potential reply from the other end
	print("receiving from sockets..")
	thread_punchers_recv = Thread(target = recv_punchers,args=(puncher_sockets,))
	thread_punchers_recv.daemon = True
	thread_punchers_recv.start()


	#punch to make endpoints on local router with remote public address of listener 
	print("punching ports..")
	for i in range(total_socks):
		if not connection_socket: 
			puncher_sockets[i].sendto(message.encode(), remote_address)
			sleep(sleep_time)
		else: #if there is a connection break
			break
	

	#if no connection wait a while to receive a potential message from the other end
	if not connection_socket:
		print("sleeping 5 sec, waiting to recv from ",remote_ip ,remote_port)
		sleep(5)


	#after a while, connection or not on current tested port, send recv_punchers stop signal to stop receiving and close all sockets
	stop_thread = True
	thread_punchers_recv.join() #wait for thread to close all sockets



###################################################################################################################################################
if len(sys.argv) < 4:
    print("Usage: puncher.py <local private ip> <remote public ip> <number of punchers>")
    print("Example: puncher.exe 192.168.1.100 7.7.7.7 1000 ")
    sys.exit()

local_ip = sys.argv[1]
remote_ip  = sys.argv[2]
total_socks = int(sys.argv[3])



global connection_socket #the winning socket that will comunicate with the listener
connection_socket = None
global remote_host #remote public ip:port of other end(listener)
remote_host = None
global stop_thread #stop signal for recv_punchers to be used from outside the thread



#read public ports provided by listener
with open('public_ports.csv') as f:
    reader = csv.reader(f)
    remote_public_ports = list(reader)

remote_public_ports = remote_public_ports[0]



packets_per_port_per_min = 15
for remote_port in remote_public_ports:
	if not connection_socket:
		print("punching port ",remote_port)
		punch_port(total_socks,local_ip,remote_ip,int(remote_port),packets_per_port_per_min)
		print("punching port ",remote_port," complete")
	else:
		break



print("keeping the connection alive...")
while True:
    message = "keep_alive"
    connection_socket.sendto(message.encode(), remote_host)
    sleep(5)

###################################################################################################################################################
#from here the user can add the code desired to use the connection, or close this program and under 30-60 sec use the 
#same local ip:local port on other program before the connection times out on the router, with 'keep alive' periodic packets sent.
#Author: Azeer Esmail