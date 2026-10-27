"""Export score seconds to an editable SMF type 1 file; no external dependency.
Tempo is fixed at 120 BPM (960 ticks/s), retaining exact source note times.
The score JSON retains local tempo/bar/chord metadata.
"""
import struct
from pathlib import Path
PROGRAMS={'piano':0,'strings':48,'pizz':45,'vibes':11}
def varlen(n):
    n=max(0,int(n)); out=[n&127];n>>=7
    while n:out.insert(0,128|(n&127));n>>=7
    return bytes(out)
def chunk(events):
    events.sort(key=lambda x:(x[0],x[1][0]&0xf0==0x90))
    data=b'';last=0
    for tick,msg in events:data+=varlen(tick-last)+msg;last=tick
    data+=b'\x00\xff\x2f\x00'
    return b'MTrk'+struct.pack('>I',len(data))+data
def write_midi(plan,path):
    tracks=[chunk([(0,b'\xff\x51\x03\x07\xa1\x20')])]
    for channel,(name,program) in enumerate(PROGRAMS.items()):
        events=[(0,bytes([0xc0|channel,program]))]
        for e in plan['notes']:
            if e['track']!=name:continue
            a=round(e['time']*960);b=max(a+1,round((e['time']+e['duration'])*960))
            events.extend([(a,bytes([0x90|channel,e['pitch'],e['velocity']])),(b,bytes([0x80|channel,e['pitch'],0]))])
        tracks.append(chunk(events))
    Path(path).write_bytes(b'MThd'+struct.pack('>IHHH',6,1,len(tracks),480)+b''.join(tracks))
