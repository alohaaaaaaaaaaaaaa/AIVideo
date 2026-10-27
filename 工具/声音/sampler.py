"""Approved GeneralUser GS sampler: only SF2 features used by this palette."""
from pathlib import Path
import struct, math
import numpy as np
from scipy import signal
SR=48000
DURATION=60.0
N=round(SR*DURATION)
def chunks(data, start, end):
    pos=start
    while pos+8<=end:
        key=data[pos:pos+4]; size=struct.unpack_from('<I',data,pos+4)[0]
        yield key,pos+8,size
        pos+=8+size+(size&1)

class Font:
    def __init__(self,path):
        d=path.read_bytes(); self.path=path
        self.parts={}
        for key,p,size in chunks(d,12,len(d)):
            if key==b'LIST':
                for name,q,n in chunks(d,p+4,p+size):self.parts[name]=d[q:q+n]
        self.samples=np.frombuffer(self.parts[b'smpl'],dtype='<i2').astype(np.float32)/32768
        def rec(name,fmt):
            st=struct.Struct(fmt); buf=self.parts[name]
            return [st.unpack_from(buf,p) for p in range(0,len(buf),st.size)]
        self.phdr=rec(b'phdr','<20sHHHIII');self.pbag=rec(b'pbag','<HH');self.pgen=rec(b'pgen','<HH')
        self.inst=rec(b'inst','<20sH');self.ibag=rec(b'ibag','<HH');self.igen=rec(b'igen','<HH')
        self.shdr=rec(b'shdr','<20sIIIIIBbHH')
    def bags(self,kind,start,end):
        bags=self.pbag if kind=='p' else self.ibag; gens=self.pgen if kind=='p' else self.igen
        out=[]
        for i in range(start,end):out.append(dict(gens[bags[i][0]:bags[i+1][0]]))
        return out
    def signed(self,x):return x if x<32768 else x-65536
    def zones(self,preset,key,vel):
        pi=next(i for i,h in enumerate(self.phdr[:-1]) if h[1]==preset and h[2]==0)
        pg={}; out=[]
        for pz in self.bags('p',self.phdr[pi][3],self.phdr[pi+1][3]):
            if 41 not in pz:pg.update(pz);continue
            pp=pg|pz
            ii=pp[41]; ig={}
            for iz in self.bags('i',self.inst[ii][1],self.inst[ii+1][1]):
                if 53 not in iz:ig.update(iz);continue
                zz=ig|iz
                ok=True
                for zone in [pp,zz]:
                    for op,val in [(43,key),(44,vel)]:
                        rr=zone.get(op,127<<8)
                        if not rr&255<=val<=rr>>8:ok=False
                if not ok:continue
                for op,v in pp.items():
                    if op not in [41,43,44]:zz[op]=(zz.get(op,0)+v)&65535
                out.append(zz)
        return out
    def note(self,preset,key,vel,duration):
        zones=self.zones(preset,key,vel)
        total=None
        for z in zones:
            h=self.shdr[z[53]]
            def val(op,default=0):return self.signed(z.get(op,default&65535))
            start=h[1]+val(0)+32768*val(4);end=h[2]+val(1)+32768*val(12)
            ls=h[3]+val(2)+32768*val(45);le=h[4]+val(3)+32768*val(50)
            root=val(58,h[6]);root=h[6] if root<0 else root
            tune=(key-root)*val(56,100)+val(51)*100+val(52)-h[7]
            step=h[5]/SR*2**(tune/1200)
            attack=max(.003,min(2,2**(val(34,-12000)/1200)))
            hold=min(1,2**(val(35,-12000)/1200))
            decay=min(8,2**(val(36,-12000)/1200))
            release=max(.055,min(1.8,2**(val(38,-12000)/1200)))
            # Long slow strings need a graceful manually shaped entrance.
            if preset==48:attack=max(.32,attack);release=max(.65,release)
            sustain=10**(-max(0,val(37))/200)
            length=min(N,round((duration+release)*SR))
            t=np.arange(length,dtype=np.float64)/SR
            idx=start+np.arange(length)*step
            mode=val(54)&3
            if mode in [1,3] and le>ls:
                loop=idx>=ls
                if mode==3:
                    release_at=round(duration*SR)
                    loop &= np.arange(length)<release_at
                    if release_at<length:
                        last=start+release_at*step
                        last=ls+(last-ls)%(le-ls) if last>=ls else last
                        idx[release_at:]=last+np.arange(length-release_at)*step
                idx[loop]=ls+(idx[loop]-ls)%(le-ls)
            valid=idx<end
            src=np.interp(np.clip(idx,start,end-1),np.arange(start,end),self.samples[start:end]).astype(np.float32)
            src[~valid]=0
            env=np.minimum(1,t/attack)
            dd=np.maximum(0,t-attack-hold)
            env*=np.where(dd<decay,1+(sustain-1)*dd/max(.001,decay),sustain)
            rix=min(len(t)-1,round(duration*SR)); level=env[rix]
            after=t>=duration
            env[after]=level*np.maximum(0,1-(t[after]-duration)/release)**1.5
            env*=np.clip((duration+release-t)/.012,0,1)
            amp=(vel/127)**1.6*10**(-max(0,val(48))/200)
            src*=env.astype(np.float32)*amp
            # SoundFont filter in cents; cap bright attacks gently for narration.
            cutoff=min(6200,8.176*2**(val(8,13500)/1200))
            if cutoff<SR*.45:src=signal.sosfilt(signal.butter(2,max(100,cutoff),fs=SR,output='sos'),src).astype(np.float32)
            pan=np.clip(val(17)/500,-1,1)
            stereo=np.stack([src*math.sqrt((1-pan)/2),src*math.sqrt((1+pan)/2)],axis=1)
            if total is None:total=stereo
            else:
                if len(total)<len(stereo):total=np.pad(total,((0,len(stereo)-len(total)),(0,0)))
                total[:len(stereo)]+=stereo
        return np.zeros((1,2),np.float32) if total is None else total

def reverb(x,decay=1.35,mix=.18,seed=6):
    rng=np.random.default_rng(seed);size=round(decay*SR)
    t=np.arange(size)/SR
    out=x.astype(np.float64).copy()
    for c in range(2):
        ir=rng.normal(0,1,size)*np.exp(-t*6/decay)
        ir=signal.sosfilt(signal.butter(2,4200,fs=SR,output='sos'),ir)
        ir[:round(.023*SR)]=0
        ir/=max(1,np.sqrt(np.sum(ir*ir)))
        for delay,amp in [(.031,.18),(.047,.12),(.079,.08)]:ir[round((delay+c*.003)*SR)]+=amp
        wet=signal.fftconvolve(x[:,c],ir)[:len(x)]
        out[:,c]+=wet*mix
    return out
