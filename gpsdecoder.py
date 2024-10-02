# Class for decoding GPS NMEA data
# See http://iosoft.blog/rtklient for details

# Copyright (c) 2024, Jeremy P Bentham
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time, serial, threading
from functools import reduce
import queue as Queue

# NMEA sentence formats
# For RMC and GGA, the last value is in NMEA version >= 4.10

RMC_S = ('id', 'time', 'status', 'lat', 'NS', 'lon', 'EW',
    'spd', 'cog', 'date', 'mv', 'mvEW', 'posMode', 'navStatus')
RMC = {RMC_S[i]: i for i in range(len(RMC_S))}

GSA_S = ('id', 'opMode', 'navMode', 'sat1', 'sat2', 'sat3', 'sat4',
    'sat5', 'sat6', 'sat7', 'sat8', 'sat9', 'sat10', 'sat11', 'sat12',
    'PDOP', 'HDOP', 'VDOP')
GSA = {GSA_S[i]: i for i in range(len(GSA_S))}

GGA_S = ('id', 'time','lat','NS','lon','EW','quality','nsats',
    'HDOP','alt','altUnit','sep','sepUnit','diffAge','diffStation')
GGA = {GGA_S[i]: i for i in range(len(GGA_S))}

qualstrs = "No fix", "GNSS fix", "GNSS fix", "?", "RTK fix", "RTK float", "Estimate"

verbose = False   # Flag to enable debug output

# Get value from GPS sentence, given variable name
def getval(data, dict, s):
    return data[dict[s]] if dict[s]<len(data) else None
    
# Convert string to integer, return default value if failed
def str2int(str, default):
    try:
        val = int(str)
    except:
        val = default
    return val

# Convert string to float, return default value if failed
def str2float(str, default):
    try:
        val = float(str)
    except:
        val = default
    return val

# Convert string with degrees & minutes to decimal degrees 
def degmin_deg(dm, nsew='N'):
    deg = 0.0
    if len(dm)>=4 and nsew in "NSEW":
        n = 2 if nsew in "NS" else 3
        deg = float(dm[:n]) + float(dm[n:]) / 60.0
        deg = -deg if nsew=='S' or nsew=='W' else deg
    return deg

# Class for GPS/GNSS NMEA decoder
class GpsDecode(object):
    def __init__(self):
        self.ser = None
        self.lat = self.lon = self.alt = self.quality = 0
        self.pdop = self.hdop = self.vdop = self.nsats = 0
        self.hour = self.min = self.sec = 0
        self.rxq = Queue.Queue()

    # Open serial port
    def ser_open(self, port, baud):
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.ser.flushInput()
        except:
            self.ser = None
        return self.ser

    # Close serial port
    def ser_close(self):
        if self.ser:
            self.receiving = False
            time.sleep(1.2)
            self.ser.close()

    # Start thread to receive serial data
    def ser_start(self):
        self.receiving = True
        self.reader = threading.Thread(target=self.ser_in, daemon=True)
        self.reader.start()

    # Blocking function to receive serial data
    def ser_in(self):
        line = b""
        while self.receiving: 
            #s = self.ser.read(self.ser.in_waiting or 1)
            if self.ser.inWaiting():
                s = self.ser.read(self.ser.in_waiting)
            #if s:
                line += s
            n = line.find(ord('\n'))
            if n >= 0:
                self.rxq.put("".join(map(chr, line[:n+1])))
                line = line[n+1:]
            else:
                time.sleep(0.001)
    
    # Write to serial port
    def ser_out(self, s):
        self.ser.write(s)

    # Poll to see if complete NMEA sentence available
    def read(self):
        line = ""
        if not self.rxq.empty():
            line = self.rxq.get().strip()
            if len(line)<9 or line[0]!='$' or line[-3]!='*':
                if verbose:
                    print("Error: %s" % line)
                line = ""
            else:
                csum = reduce(lambda x,y: x^y, [ord(c) for c in line[1:-3]], 0)
                if csum != int(line[-2:], 16):
                    print("Checksum error: %s" % line)
                    line = ""
        return line
            
    # Decode NMEA sentence, return true if new position
    def decode(self, line):
        data = line[:-3].split(',')
        if len(data) < 3:
            return ""
        if verbose:
            print(line)
            
        # GSA: active satellites and DOP values
        if (data[0]=='$GPGSA' or data[0]=='$GNGSA'):
            self.pdop = str2float(getval(data, GSA, "PDOP"), 99.99)
            self.hdop = str2float(getval(data, GSA, "HDOP"), 99.99)
            self.vdop = str2float(getval(data, GSA, "VDOP"), 99.99)
        
        # GGA: time, position, altitude and GPS quality
        elif data[0]=='$GPGGA' or data[0]=='$GNGGA':
            t = getval(data, RMC, "time")
            self.hour = str2int(t[0:2], 0)
            self.min = str2int(t[2:4], 0)
            self.sec = str2float(t[4:], 0)

            self.lat = degmin_deg(getval(data, GGA, "lat"), getval(data, GGA, "NS"))
            self.lon = degmin_deg(getval(data, GGA, "lon"), getval(data, GGA, "EW"))
            self.quality = str2int(getval(data, GGA, "quality"), 0)
            self.nsats = str2int(getval(data, GGA, "nsats"), 0)
            self.hdop = str2float(getval(data, GGA, "HDOP"), 99.99)
            self.alt = str2float(getval(data, GGA, "alt"), 0)
            return True
        return False
        
    # Return time string
    def timestr(self):
        return "%02u:%02u:%02u" % (self.hour, self.min, int(self.sec))

    # Return position string
    def postr(self):
        return "%10.8f,%10.8f,%5.3f" % (self.lat, self.lon, self.alt)
        
    # Return quality string
    def qualstr(self):
        return qualstrs[self.quality] if self.quality < len(qualstrs) else "?"
    
# EOF
