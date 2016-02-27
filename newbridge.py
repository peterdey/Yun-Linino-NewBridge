#!/usr/bin/env python
# encoding: utf-8
#
# Copyright (c) 2010 Doug Hellmann.  All rights reserved.
#
"""Server half of echo example.
"""
#end_pymotw_header

import select
import socket
import sys
import Queue
import logging

# Set up logging
logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', "%Y-%m-%d %H:%M:%S")
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.FileHandler('newbridge.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Create a TCP/IP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setblocking(0)

# Bind the socket to the port
server_address = ('localhost', 10000)
logger.info('starting up on %s port %s' % server_address)
server.bind(server_address)

# Listen for incoming connections
server.listen(5)

# Sockets from which we expect to read
inputs = [ server ]

# Sockets to which we expect to write
outputs = [ ]

# Outgoing message queues (socket:Queue)
message_queues = {}

while inputs:

    # Wait for at least one of the sockets to be ready for processing
    logger.debug('waiting for the next event')
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    # Handle inputs
    for s in readable:

        if s is server:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            logger.info('new connection from %s', client_address)
            connection.setblocking(0)
            inputs.append(connection)

            # Give the connection a queue for data we want to send
            message_queues[connection] = Queue.Queue()

        else:
            data = s.recv(1024)
            if data:
                # A readable client socket has data
                logger.debug('received "%s" from %s' % (data, s.getpeername()))
                message_queues[s].put(data)
                # Add output channel for response
                if s not in outputs:
                    outputs.append(s)
                    
            else:
                # Interpret empty result as closed connection
                logger.info('closing %s after reading no data', client_address)
                # Stop listening for input on the connection
                if s in outputs:
                    outputs.remove(s)
                inputs.remove(s)
                s.close()

                # Remove message queue
                del message_queues[s]

    # Handle outputs
    for s in writable:
        try:
            next_msg = message_queues[s].get_nowait()
        except Queue.Empty:
            # No messages waiting so stop checking for writability.
            logger.debug('output queue for %s is empty', s.getpeername())
            outputs.remove(s)
        else:
            logger.debug('sending "%s" to %s' % (next_msg, s.getpeername()))
            s.send(next_msg)

    # Handle "exceptional conditions"
    for s in exceptional:
        logger.warn('handling exceptional condition for %s', s.getpeername())
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()

        # Remove message queue
        del message_queues[s]
