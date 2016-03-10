# Yun-Linino-NewBridge
A lightweight, highly stable replacement for the Yún's out-of-the-box bridge.

Works best when partnered with [Yun-MCU-NewBridge](https://github.com/peterdey/Yun-MCU-NewBridge), but will work with any sketch that talks to Serial1.

## Features:
* Pluggable modular architecture for dealing with incoming data.  Send data off to a log file or syslog as you please.
* Runs at native baud rate of the Yún's serial line (250kbps)
* No need to hack pySerial to run at faster baud rates
* No serial initialisation required

## MySensors integration (see "mysensors" branch)
* For use with the [MySensors](http://www.mysensors.org) library
* Supports pushing sensor data to [collectd](https://collectd.org/)
* Works with the [SerialGateway.ino](https://github.com/mysensors/Arduino/blob/master/libraries/MySensors/examples/SerialGateway/SerialGateway.ino) sketch, with appropriate modifications to get it to use Serial1 (defaults to using Serial) 

## Usage
Copy the files to somewhere on the Linino side of your Yún.  If you plan to log to a file, a SD card is highly recommended, to prevent excessive flash wear.

Two options for invocation: edit `/etc/inittab`, or invoke from your Sketch.

### Option 1: /etc/inittab
Open up `/etc/inittab`, and replace this:
```
ttyATH0::askfirst:/bin/ash --login
```
with:
```
ttyATH0::respawn:/path/to/newbridge.py -q -l /full/path/to/logfile.log
```
Your sketch should initialise Serial1 at 250kbps, then can simply shuffle data over Serial1:
```
void setup()  { 
    Serial1.begin(250000);
    Serial1.println("Hello NewBridge!");
}
```
### Option 2: Invoke  from your sketch
In its default configuration, the Linino side of the Yún presents a busybox shell to the MCU on Serial1, at 250kbps.

Briefly, your sketch should:
* Wait until Linino finishes booting, so you don't interfere with the boot process (Arduino's Bridge code says 2500ms is the minimum time)
* Initialise Serial1 at 250kbps: `Serial1.begin(250000);`
* Send a carriage return to start the console
* Invoke NewBridge at the prompt presented, e.g. `/path/to/newbridge.py -q -l /full/path/to/logfile.log`

[Yun-MCU-NewBridge](https://github.com/peterdey/Yun-MCU-NewBridge) uses this method (in addition to first terminating the Arduino Bridge if it happens to be running).
