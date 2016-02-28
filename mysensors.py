# encoding: utf-8
#
# New Bridge for Arduino Yún.
# MySensors message broker for Linino side
#
# Copyright (c) 2016 Peter Dey.  All rights reserved.
#

import logging
import socket
import fcntl
import errno
from abc import ABCMeta, abstractmethod

class MySensors():
    
    def __init__(self, logger):
        self.logger = logger
        self.buffer = ""
        self.listeners = [ ]

    def newdata (self, incoming):
        self.buffer += incoming
        while "\n" in self.buffer:
            (line, self.buffer) = self.buffer.split("\n", 1)
            self.parseline(line)
    
    def parseline (self, line):
        self.logger.debug("mysensors: %s", line)
        if line.count(';') >= 5:
             # Probably valid MySensors Serial API message
             for listener in self.listeners:
                 listener.process(line)
            
    def addListener (self, listener):
        listener._setLogger(self.logger)
        self.listeners.append(listener)
        
class Listener():
    __metaclass__ = ABCMeta
    
    def __init__(self):
        self.logger = None
    
    def _setLogger(self, logger):
        self.logger = logger
    
    @abstractmethod
    def process(self):
        pass

class CollectdListener(Listener):
    
    def process(self, line):
        _splitresponse = line.split(";", 5)
        n, c, m, a, s, p = _splitresponse
        if not (int(m)==1 or (int(c)==255 and int(m)==3 and int(a)==0 and int(s)==0)):
            return
        
        try:
            fp = open('/var/run/collectd.lock', 'w')
            fcntl.lockf(fp, fcntl.LOCK_EX)
        except IOError:
            self.logger.error("can't obtain lock on /var/run/collectd.lock")
            return
        
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect('/var/run/collectd-unixsock')
        except socket.error as e:
            if e.errno == errno.ENOENT:
                self.logger.error("Can't open collectd unixsock: collectd is probably not running")
                return
        
        #sock.send("PUTVAL mysensors/node" + n + "/gauge-sensor" + c + " interval=60 " + str(time.time()) + ":" + str(float(p)) + "\n")
        self.logger.info("collectd: PUTVAL mysensors/node" + n + "/gauge-sensor" + c + " N:" + p)
        sock.sendall("PUTVAL mysensors/node" + n + "/gauge-sensor" + c + " N:" + p + "\n")
        #sock.sendall("FLUSH\n")

        # Clear out the socket's receive buffer
        retval = ""
        while not "\n" in retval:
            retval += sock.recv(1024)

        self.logger.debug("collectd: %s", retval.strip())
        sock.close()
        
        fcntl.lockf(fp, fcntl.LOCK_UN)

class TraceLogListener(Listener):
    
    def process(self, line):
        _splitresponse = line.split(";", 5)
        n, c, m, a, s, p = _splitresponse
        if not (int(c)==255 and int(m)==3 and int(a)==0 and int(s)==9):
            return
        
        self.logger.warn("Node %s: %s", n, p)

if __name__ == '__main__':
    logger = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', "%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('sensorlog.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    ms = MySensors(logger)
    ms.addListener(CollectdListener())
    ms.addListener(TraceLogListener())
    
    ms.newdata("1;255;3;0;9;Awake.\n")
    ms.newdata("1;255;3;0;0;93\n1;4;1;0;0;29.2\n")
    ms.newdata("1;0;1;0;1;")
    ms.newdata("310.0\n1;1;1;0;0;18.6\n")
