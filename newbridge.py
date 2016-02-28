#!/usr/bin/env python
# encoding: utf-8
#
# New Bridge for Arduino Yún.
#
# Copyright (c) 2016 Peter Dey.  All rights reserved.
#
# Derived from select_echo_server.py
# Copyright (c) 2010 Doug Hellmann.  All rights reserved.
#

import select
import socket
import sys
import Queue
import logging
import fcntl
import os
import signal
import argparse
import queuehandler
import termios
import atexit

# Add usage and arguments for our options
parser = argparse.ArgumentParser(description='New Bridge for Arduino Yún')

parser.add_argument(
    '-q', '--quiet',
    action='store_true',
    help="don't print anything to the console",
    default=False)

parser.add_argument(
    '-d', '--debug',
    action='store_true',
    help='increase logging level (both to console and logfile)',
    default=False)

parser.add_argument(
    '-P', '--port',
    type=int,
    help='local TCP port to listen on (default: 6571)',
    default=6571)

parser.add_argument(
    '-l', '--log',
    help='file to log to (default: log.log)',
    default='log.log')

args = parser.parse_args()

# Function to enable/disable local terminal echo.
def enable_echo(fd, enabled):
       (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) \
                     = termios.tcgetattr(fd)
       if enabled:
               lflag |= termios.ECHO
       else:
               lflag &= ~termios.ECHO
       new_attr = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
       termios.tcsetattr(fd, termios.TCSANOW, new_attr)

# disable terminal echo
enable_echo(sys.stdin.fileno(), False)
atexit.register(enable_echo, sys.stdin.fileno(), True)

# make stdin a non-blocking file
fd = sys.stdin.fileno()
fl = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

# Set up logging
logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', "%Y-%m-%d %H:%M:%S")

if args.debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

q = Queue.Queue(-1)
qh = queuehandler.QueueHandler(q)
fh = logging.FileHandler(args.log)
ql = queuehandler.QueueListener(q, fh)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(qh)
ql.start()

# Don't send anything to the console if we're asked to be quiet
if not args.quiet:
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Catch the Keyboard Interrupt
def signal_handler(signal, frame):
    logger.warn('caught Ctrl+C.  Terminating.')
    ql.stop()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

# Create a TCP/IP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.setblocking(0)

# Bind the socket to the port
server_address = ('', args.port)
logger.warn('pid %s starting up on port %s', os.getpid(), server_address)
server.bind(server_address)

# Listen for incoming connections
server.listen(5)

# Sockets from which we expect to read
inputs = [ sys.stdin, server ]

# Sockets to which we expect to write
outputs = [ ]

# Outgoing message queues (socket:Queue)
message_queues = {}

# Queue for stdout
message_queues[sys.stdout] = Queue.Queue()

while inputs:

    # Wait for at least one of the sockets to be ready for processing
    logger.debug('waiting for the next event')
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    # Handle inputs
    for s in readable:

        if s is server:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            logger.warn('new connection from %s', client_address)
            connection.setblocking(0)
            inputs.append(connection)

            # Give the connection a queue for data we want to send
            message_queues[connection] = Queue.Queue()
        
        elif s is sys.stdin:
            # Relay data from stdin to all clients
            data = sys.stdin.read(1024)
            logger.info('sys.stdin: %s', data.strip())
            if '\x04' in data:
                logger.warn('got Ctrl+D.  Terminating.')
                raise KeyboardInterrupt
            for client in inputs:
                if client is not sys.stdin and client is not server:
                    message_queues[client].put(data)
                    # Add output channel for response
                    if s not in outputs:
                        outputs.append(client)        
        
        else:
            data = s.recv(1024)
            if data:
                # A readable client socket has data
                # Relay data from any client to stdout
                logger.info('%s: %s', s.getpeername(), data.strip())
                message_queues[sys.stdout].put(data)
                if sys.stdout not in outputs:
                    outputs.append(sys.stdout)
                    
            else:
                # Interpret empty result as closed connection
                logger.warn('closing %s after reading no data', client_address)
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
            if s is sys.stdout:
                sys.stdout.flush()
                logger.debug('output queue for stdout is empty')
            else:
                logger.debug('output queue for %s is empty', s.getpeername())
            outputs.remove(s)
        else:
            if s is sys.stdout:
                logger.debug('writing "%s" to stdout' % next_msg)
                s.write(next_msg)
            else:
                logger.debug('sending "%s" to %s' % (next_msg, s.getpeername()))
                s.send(next_msg)

    # Handle "exceptional conditions"
    for s in exceptional:
        logger.error('handling exceptional condition for %s', s.getpeername())
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()

        # Remove message queue
        del message_queues[s]
