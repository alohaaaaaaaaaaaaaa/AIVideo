"""Accepted voice-preserving ducking helpers. No paid service."""
import subprocess
import numpy as np
from scipy import signal
import imageio_ffmpeg
FF=imageio_ffmpeg.get_ffmpeg_exe()
RATE=48000
DURATION=60.0
N=round(RATE*DURATION)
def run(args):
    p=subprocess.run([FF,'-hide_banner','-y',*map(str,args)],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-4000:])
    return p

def decode(path,channels,filters=None):
    args=['-v','error','-i',path,'-vn']
    if filters:args+=['-af',filters]
    args+=['-ac',channels,'-ar',RATE,'-f','f32le','pipe:1']
    a=np.frombuffer(run(args).stdout,dtype='<f4').reshape(-1,channels).copy()
    if len(a)<N:a=np.pad(a,((0,N-len(a)),(0,0)))
    return a[:N]

def rms_frames(a,block):
    if a.ndim==1:a=a[:,None]
    count=len(a)//block
    return np.sqrt(np.mean(np.sum(a[:count*block].reshape(count,block,-1)**2,axis=2),axis=1)+1e-18)

def db(x):return 20*np.log10(np.maximum(x,1e-12))

def band(a,lo=1000,hi=3000):
    return signal.sosfilt(signal.butter(3,[lo,hi],btype='bandpass',fs=RATE,output='sos'),a,axis=0)
