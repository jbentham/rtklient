# Interface to an NTRIP caster
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

import socket, select, base64, signal, math, sys, time

SOCK_TIMEOUT        = 5.0
CLIENT_NAME         = "rtklient"
CLIENT_VERSION      = "008"
SOURCE_NAME         = "Demo1"
HOST_URL            = "127.0.0.1"
HOST_PORTNUM        = 2101
RTCM_START          = 0xd3
BLOCK_MAX           = 1030

verbose = False

# Lookup table for 24-bit CRC
CRC24_TABLE = (
    0x000000, 0x864cfb, 0x8ad50d, 0x0c99f6, 0x93e6e1, 0x15aa1a, 0x1933ec, 0x9f7f17,
    0xa18139, 0x27cdc2, 0x2b5434, 0xad18cf, 0x3267d8, 0xb42b23, 0xb8b2d5, 0x3efe2e,
    0xc54e89, 0x430272, 0x4f9b84, 0xc9d77f, 0x56a868, 0xd0e493, 0xdc7d65, 0x5a319e,
    0x64cfb0, 0xe2834b, 0xee1abd, 0x685646, 0xf72951, 0x7165aa, 0x7dfc5c, 0xfbb0a7,
    0x0cd1e9, 0x8a9d12, 0x8604e4, 0x00481f, 0x9f3708, 0x197bf3, 0x15e205, 0x93aefe,
    0xad50d0, 0x2b1c2b, 0x2785dd, 0xa1c926, 0x3eb631, 0xb8faca, 0xb4633c, 0x322fc7,
    0xc99f60, 0x4fd39b, 0x434a6d, 0xc50696, 0x5a7981, 0xdc357a, 0xd0ac8c, 0x56e077,
    0x681e59, 0xee52a2, 0xe2cb54, 0x6487af, 0xfbf8b8, 0x7db443, 0x712db5, 0xf7614e,
    0x19a3d2, 0x9fef29, 0x9376df, 0x153a24, 0x8a4533, 0x0c09c8, 0x00903e, 0x86dcc5,
    0xb822eb, 0x3e6e10, 0x32f7e6, 0xb4bb1d, 0x2bc40a, 0xad88f1, 0xa11107, 0x275dfc,
    0xdced5b, 0x5aa1a0, 0x563856, 0xd074ad, 0x4f0bba, 0xc94741, 0xc5deb7, 0x43924c,
    0x7d6c62, 0xfb2099, 0xf7b96f, 0x71f594, 0xee8a83, 0x68c678, 0x645f8e, 0xe21375,
    0x15723b, 0x933ec0, 0x9fa736, 0x19ebcd, 0x8694da, 0x00d821, 0x0c41d7, 0x8a0d2c,
    0xb4f302, 0x32bff9, 0x3e260f, 0xb86af4, 0x2715e3, 0xa15918, 0xadc0ee, 0x2b8c15,
    0xd03cb2, 0x567049, 0x5ae9bf, 0xdca544, 0x43da53, 0xc596a8, 0xc90f5e, 0x4f43a5,
    0x71bd8b, 0xf7f170, 0xfb6886, 0x7d247d, 0xe25b6a, 0x641791, 0x688e67, 0xeec29c,
    0x3347a4, 0xb50b5f, 0xb992a9, 0x3fde52, 0xa0a145, 0x26edbe, 0x2a7448, 0xac38b3,
    0x92c69d, 0x148a66, 0x181390, 0x9e5f6b, 0x01207c, 0x876c87, 0x8bf571, 0x0db98a,
    0xf6092d, 0x7045d6, 0x7cdc20, 0xfa90db, 0x65efcc, 0xe3a337, 0xef3ac1, 0x69763a,
    0x578814, 0xd1c4ef, 0xdd5d19, 0x5b11e2, 0xc46ef5, 0x42220e, 0x4ebbf8, 0xc8f703,
    0x3f964d, 0xb9dab6, 0xb54340, 0x330fbb, 0xac70ac, 0x2a3c57, 0x26a5a1, 0xa0e95a,
    0x9e1774, 0x185b8f, 0x14c279, 0x928e82, 0x0df195, 0x8bbd6e, 0x872498, 0x016863,
    0xfad8c4, 0x7c943f, 0x700dc9, 0xf64132, 0x693e25, 0xef72de, 0xe3eb28, 0x65a7d3,
    0x5b59fd, 0xdd1506, 0xd18cf0, 0x57c00b, 0xc8bf1c, 0x4ef3e7, 0x426a11, 0xc426ea,
    0x2ae476, 0xaca88d, 0xa0317b, 0x267d80, 0xb90297, 0x3f4e6c, 0x33d79a, 0xb59b61,
    0x8b654f, 0x0d29b4, 0x01b042, 0x87fcb9, 0x1883ae, 0x9ecf55, 0x9256a3, 0x141a58,
    0xefaaff, 0x69e604, 0x657ff2, 0xe33309, 0x7c4c1e, 0xfa00e5, 0xf69913, 0x70d5e8,
    0x4e2bc6, 0xc8673d, 0xc4fecb, 0x42b230, 0xddcd27, 0x5b81dc, 0x57182a, 0xd154d1,
    0x26359f, 0xa07964, 0xace092, 0x2aac69, 0xb5d37e, 0x339f85, 0x3f0673, 0xb94a88,
    0x87b4a6, 0x01f85d, 0x0d61ab, 0x8b2d50, 0x145247, 0x921ebc, 0x9e874a, 0x18cbb1,
    0xe37b16, 0x6537ed, 0x69ae1b, 0xefe2e0, 0x709df7, 0xf6d10c, 0xfa48fa, 0x7c0401,
    0x42fa2f, 0xc4b6d4, 0xc82f22, 0x4e63d9, 0xd11cce, 0x575035, 0x5bc9c3, 0xdd8538)

# Return 24-bit CRC of data bytes 
def crc24(data):
    val = 0
    for byte in data:
        val = (val << 8) ^ CRC24_TABLE[byte ^ ((val >> 16) & 0xff)]
    return val & 0xffffff
   
# Get 2s complement number from the given offset & number of bits
def getbits2(a, oset, nbits):
    res = 0
    for n in range(oset, oset+nbits):
        byt, bit = n // 8, 7 - (n & 7)
        res = (res << 1) | ((a[byt] >> bit) & 1)
    if res & (1 << (nbits - 1)):
        res = res - (1 << nbits)
    return res        

# Get index of byte in data, negative if not found
def bin_index(data, b):
    try:
        idx = data.index(b)
    except:
        idx = -1
    return(idx)
    
#  Calculate distance in kilometers between two points in decimal degrees
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1 
    a = math.sin(dlat/2.0)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2.0)**2
    return 2 * math.asin(math.sqrt(a)) * 6371

# Class for NTRIP decoding
class NtripDecode(object):
    def __init__(self):
        self.sock = self.host = self.port = None
        self.data = b""
        self.msg_types = []
        self.casters = []
        self.sources = {}
        
    # Open a TCP socket
    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(SOCK_TIMEOUT)
    
    # Make TCP connection
    def connect(self, host, port):
        self.host, self.port = host, port
        return self.sock.connect((host, port))

    # Close TCP connection
    def close(self):
        if self.sock:
            self.sock.close()
        self.sock = None

    # Send data to TCP socket
    def send(self, data):
        return self.sock.send(data.encode())
        
    # Poll socket for receive data (non-blocking)
    def poll(self):
        sel = select.select([self.sock], [], [], 0)
        return self.sock.recv(BLOCK_MAX) if sel[0] else None
        
    # Receive text from TCP socket
    def receive_text(self):
        text = ""
        part = "."
        while part:
            try:
                part = self.sock.recv(BLOCK_MAX).decode()
                text += part
            except:
                break
        return text
    
    # Receive CRLF-terminated line from TCP socket
    def receive_line(self):
        line = ""
        while "\n" not in line:
            try:
                part = self.sock.recv(BLOCK_MAX).decode()
                line += part
            except:
                break
        return line
        
    # Get next message from data
    # If first char is not RTCM_START, then message is a text string
    def get_msg(self):
        d = b""
        idx = bin_index(self.data, RTCM_START)  # Get start of RTCM block
        if idx>3 and self.data[idx-2]==0xd and self.data[idx-1]==0xa:
            d = self.data[0:idx]                # If text before RTCM..
            self.data = self.data[idx:]         # ..return text
        elif idx == 0 and len(self.data) > 2:   # Get length word
            n = (self.data[1] << 8) + self.data[2]
            if n > 1024:                        # ..check if valid
                d = self.data = b""             # Scrub data if invalid
            elif len(self.data) >= n + 6:       # If sufficient data received..
                d = self.data[0:n+6]            # ..get data
                crc = crc24(d)                  # ..check CRC
                if crc == 0:                    # If OK, remove data from store
                    self.data = self.data[len(d):]
                else:
                    print("CRC error")
                    d = self.data = b""
        elif idx > 0:
            print("Extra data")
            self.data = self.data[idx:]
        return d

    # Get RTCM data block, or text string (as bytes)
    def receive_rtcm(self):
        part = self.poll()                      # Get next data block
        if part:                                # Stop if no more data
            self.data += part                   # Append data to previous
        return self.get_msg()                   # Get message
        
    # Request a resource from the NTRIP server
    def request(self, target, user=None):
        req = "GET /%s HTTP/1.0\r\n" % target
        req += "Host: %s:%u\r\n" % (self.host, self.port)
        req += "User-Agent: NTRIP %s/%s\r\n" % (CLIENT_NAME, CLIENT_VERSION)
        req += "Accept: */*\r\nConnection: close\r\n"
        if user:
            req += "Authorization: Basic "
            req += base64.b64encode(user.encode()).decode()
            req += "\r\n"
        self.send(req + "\r\n")
    
    # Get the source table, return number of entries
    def get_sourcetable(self, country=None):
        c = ";%s;" % country.upper() if country else ";"
        self.request("")
        table = self.receive_text()
        lines = table.split("\n")
        self.sourcelines = [line for line in lines
            if line.startswith("STR;") and c in line]
        self.sources = {}
        for line in self.sourcelines:
            country, name, lat, lon = get_sourcetable_name_pos(line)
            self.sources[name] = country, lat, lon
        return len(self.sourcelines)
        
    # Get RTCM message type, 0 if error
    def msg_type(self, data):
        typ = 0 if data[0] != RTCM_START else (data[3] << 4) + (data[4] >> 4)
        if typ and typ not in self.msg_types:
            self.msg_types.append(typ)
        return typ
            
    # Return string with message types
    def msg_types_str(self, typ):
        s = ""
        self.msg_types.sort()
        for t in self.msg_types:
            s += "[%u]" % t if t == typ else " %u " % t
        return s
    
# Get country, name, lat, lon from line of sourcetable
def get_sourcetable_name_pos(line):
    data = line.split(';')
    if len(data) > 10:
        try:
            return data[8], data[1], float(data[9]), float(data[10])
        except:
            pass
    return "", "", 0, 0

# Get 2s complement number from the given offset & number of bits
def getbits2(a, oset, nbits):
    res = 0
    for n in range(oset, oset+nbits):
        byt, bit = n // 8, 7 - (n & 7)
        res = (res << 1) | ((a[byt] >> bit) & 1)
    if res & (1 << (nbits - 1)):
        res = res - (1 << nbits)
    return res        

# Convert ECEF coordinates into lat, lon and height in metres
def xyz_llh(x, y, z):
    if not (x or y or z):
        return 0, 0, 0
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a - f*a
    e = math.sqrt(a*a - b*b) / a
    clambda = math.atan2(y, x)
    p = math.sqrt(x*x + y*y)
    h_old = 0.0
    theta = math.atan2(z, p * (1.0 - e*e))
    cs = math.cos(theta)
    sn = math.sin(theta)
    N = a * a / math.sqrt(math.pow(a*cs, 2) + math.pow(b*sn, 2))
    h = p/cs - N
    while abs(h-h_old) > 1.0e-6:
        h_old = h
        theta = math.atan2(z, p*(1.0 - e*e * N / (N + h)))
        cs = math.cos(theta)
        sn = math.sin(theta)
        N = a * a / math.sqrt(math.pow(a*cs, 2) + math.pow(b*sn, 2))
        h = p/cs - N
    return math.degrees(theta), math.degrees(clambda), h

# Get lat, lon and height from RTCM 1005 or 1006 message    
def decode_1006(data):
    res = 0, 0, 0
    msg_num = getbits2(data[3:], 0, 12);
    if msg_num == 1005 or msg_num == 1006:
        x = getbits2(data[3:], 34, 38) * 0.0001
        y = getbits2(data[3:], 74, 38) * 0.0001
        z = getbits2(data[3:], 114, 38) * 0.0001
        res = xyz_llh(x, y, z)
    return res
    
# Handle ctrl-C
def break_handler(sig, frame):
    global types, start
    dt = time.time() - start
    print("\r\nCollected data for %3.1f seconds" % dt)
    print("Closing...")
    ntrip.close()
    exit(1)
    
if __name__ == "__main__":
    
    caster_name = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        posn = float(sys.argv[2]), float(sys.argv[3])
    except:
        posn = None
    
    ntrip = NtripDecode()
    signal.signal(signal.SIGINT, break_handler)
    
    ntrip.open()
    print("Connecting to %s:%u" % (HOST_URL, HOST_PORTNUM))
    ntrip.connect(HOST_URL, HOST_PORTNUM)
    n = ntrip.get_sourcetable()
    ntrip.close()
    print("%u sourcetable entries" % n)
    if posn:
        for source in ntrip.sourcelines:
            name, lat, lon = get_sourcetable_name_pos(source)
            if lat and lon:
                dist = haversine(posn[0], posn[1], lat, lon)
                print("%10s %9.3f km" % (name, dist))
                
    print("Fetching data from '%s'" % SOURCE_NAME)
    ntrip.open()
    ntrip.connect(HOST_URL, HOST_PORTNUM)
    ntrip.request(SOURCE_NAME)
    pos = ""
    dlen = 0
    start = time.time()
    types = {}
    print("Counting message types (ctrl-C to exit)..")
    while SOURCE_NAME:
        d = ntrip.receive_rtcm()
        if d and d[0] == RTCM_START:
            dlen += len(d)
            typ = ntrip.msg_type(d)
            types[typ] = 1 if typ not in types else types[typ] + 1
            keys = sorted(types.keys())
            s = ", ".join([("%u:%u" % (key, types[key])) for key in keys])
            print(s, end ="\r")
        elif d:
            print(d.decode().strip())
        time.sleep(0.001)
# EOF

    