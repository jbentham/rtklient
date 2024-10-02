# RTK client: get NTRIP data from caster, and GNSS data from serial link
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

# v0.14 JPB 17/9/24 Corrected GGA transmission
# v0.15 JPB 2/10/24 Removed default mount point
# v0.16 JPB 2/10/24 Removed default user

import sys, time, signal, argparse
import gpsdecoder, ntripdecoder

DEFAULT_BAUD   = 115200                 # Default baud rate
DEFAULT_COM    = ""                     # Default COM port name
DEFAULT_PORT   = 2101                   # Default NTRIP server port
DEFAULT_COUNTRY= ""                     # Default 3-letter country
DEFAULT_USER = ""                       # Default user and password
#DEFAULT_SERVER = "127.0.0.1"            # Local NTRIP server (SNIP)
DEFAULT_SERVER = "rtk2go.com"           # rtk2go NTRIP server
verbose = False

# Handle console ctrl-C
def break_handler(sig, frame):
    print("\r\nClosing...")
    if ntrip and ntrip.sock:
        ntrip.close()
    exit(1)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument( "--lat",       type=float,metavar="DEG",help="latitude (decimal degrees)")
    parser.add_argument( "--lon",       type=float,metavar="DEG",help="longitude (decimal degrees)")
    parser.add_argument("--country",               metavar="STR",help="country name (3 letters)", default=DEFAULT_COUNTRY)
    parser.add_argument("-f", "--find",            action="store_const", const=True, default=False, help="find nearest source")
    parser.add_argument("-v", "--verbose",         action="store_const", const=True, default=False, help="verbose mode")

    parser.add_argument("-b", "--baud", type=int,  metavar="NUM",help="GPS com port baud rate", default=DEFAULT_BAUD)
    parser.add_argument("-c", "--com",             metavar="STR",help="GPS com port name", default=DEFAULT_COM)
    parser.add_argument("-m", "--mount",           metavar="STR",help="NTRIP mount point (stream name)")
    parser.add_argument("-p", "--port", type=int,  metavar="NUM",help="NTRIP server port number", default=DEFAULT_PORT)
    parser.add_argument("-s", "--server",          metavar="URL",help="NTRIP server URL", default=DEFAULT_SERVER)
    parser.add_argument("-u", "--user",            metavar="STR",help="NTRIP user (name:password)", default=DEFAULT_USER)
   
    args = parser.parse_args()
    verbose = gpsdecoder.verbose = ntripdecoder.verbose = args.verbose
    gps = gpsdecoder.GpsDecode()
    ntrip = ntripdecoder.NtripDecode()
    
    # Open serial port, wait for position
    if args.com:
        if not gps.ser_open(args.com, args.baud):
            print("Can't open serial port %s" % args.com)
            sys.exit(1)
        print("Opening port %s at %u baud" % (args.com, args.baud))
        signal.signal(signal.SIGINT, break_handler)
        gps.ser_start()
        print("Waiting for GPS position (ctrl-C to exit)..")
        postr = ""
        while True:
            line = gps.read()
            if line and gps.decode(line):
                postr = gps.postr()
                if postr:
                    print("%s %s %s  " % (gps.timestr(), postr, gps.qualstr()), end = '\r')
                if gps.lat and gps.lon:
                    print("")
                    break
            else:
                time.sleep(0.001)
        
    # No serial interface, use command-line position
    elif args.lat and args.lon:
        print("Using fixed position %1.8f,%1.8f" % (args.lat, args.lon))
        gps.lat, gps.lon = args.lat, args.lon
    else:
        print("Position unknown; use --com for GPS serial, or --lat and --lon")
        sys.exit(1)
    
    # Connect to NTRIP server
    if args.server:
        print("Contacting NTRIP server '%s'" % args.server)
        ntrip.open()
        try:
            ntrip.connect(args.server, args.port)
        except:
            print("Can't connect to '%s:%u'" % (args.server, args.port))
            sys.exit(1)
        n = ntrip.get_sourcetable(args.country)
        ntrip.close()
        c = "(country '%s')" %args.country if args.country else ""
        print("%d source table entries %s" % (n, c))
    
    # Find nearest RTK source
    if args.find:
        print("Finding nearest mount point")
        dists = {}
        for mount in ntrip.sources:
            country, lat, lon = ntrip.sources[mount]
            if lat and lon:
                dist = ntripdecoder.haversine(gps.lat, gps.lon, lat, lon)
                dists[mount] = dist, country
        if not dists:
            print("No mount points found")
        else:
            srt = dict(sorted(dists.items(), key=lambda x: x[1]))
            nearest = {k: srt[k] for k in list(srt)[:5]}
            for mount in nearest.keys():
                print("  %03s %20s %8.1f km" % (dists[mount][1], mount, dists[mount][0]))
        sys.exit(0)
    
    # Open RTCM data stream
    if args.server:
        if not args.mount:
            print("Mount point not set: use --mount")
            exit(1)
        if args.mount not in ntrip.sources:
            print("Mount point '%s' not found in %s" % (args.mount, args.server))
            exit(1)
        if not args.user:
            print("Username not set: should be email:passwd")
            exit(1)
        print("Fetching RTCM data from %s (ctrl-C to exit)" % args.mount)
        ntrip.open()
        ntrip.connect(args.server, args.port)
        ntrip.request(args.mount, args.user)

        # Loop printing GPS data
        gga_count = msg_type = dist = nlat = nlon = nht = mind = maxd = 0
        postr = ""
        while args.com:
            if args.server and args.mount:
                rtcm = ntrip.receive_rtcm()
                if rtcm and gps.lat and gps.lon:
                    msg_type = ntrip.msg_type(rtcm)
                    if msg_type == 1005 or msg_type == 1006:
                        nlat, nlon, nht = ntripdecoder.decode_1006(rtcm)
                    gps.ser_out(rtcm)
            line = gps.read()
            if line:
                if gps.decode(line):
                    postr = gps.postr()
                    if gga_count % 30 == 0:
                        ntrip.send(line + "\r\n")
                    gga_count += 1
                if postr:
                    dist = ntripdecoder.haversine(gps.lat, gps.lon, nlat, nlon) if nlat or nlon else 0
                    print("%s Pos %s " % (gps.timestr(), postr), end = '')
                    print("RTCM %4u " % msg_type, end = '')
                    print("Dist %6.3f " % (dist*1000), end = '')
                    print("%s " % gps.qualstr(), end = '')
                    if gps.quality == 4:
                        mind = min(mind, dist) if mind else dist
                        maxd = max(maxd, dist)
                        print("Diff %5.3f " % ((maxd-mind)*1000), end='')
                    print("   ", end='\r')
            else:
                time.sleep(0.001)
    gps.ser_close()

# EOF
