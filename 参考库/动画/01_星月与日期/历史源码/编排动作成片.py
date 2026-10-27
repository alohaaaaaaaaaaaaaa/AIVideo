"""以真实配音边界留出查证时间；不改变字音速度，不调用API。"""
from pathlib import Path
import json
import math
import numpy as np
from scipy.io import wavfile

BASE=Path(__file__).resolve().parents[1];SECTION=BASE.parent
RATE=48000;FPS=25
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def q(t):return round(t*FPS)/FPS

# 在短语之后已有静音中插入阅读/动作时间，切点用相邻实际词边界中点。
HOLDS={
'B01':{'再放进机场附近的经纬度。':.8,'方向和高度。':1.4,'地平线上方十度左右。':.6},
'B02':{'报道说的是机场东南面。':.8,'它在身后的西偏北。':.6},
'B03':{'同样在下面。':.5,'可万一，报道里的时间差了点呢？':.6,'金星还慢慢落了下去。':.8,'在已核对的时间里都没升上来。':.6},
'B04':{'坐等奥特曼现身。':.7,'奥特曼先等等。':2.5},
'B05':{'看见了吗？':.6,'新疆的另一则传闻。':.6,'再找美国航天局的任务记录。':1.,'六月三十日，':.4,'再把日历翻到萧山这晚，':2.8,'已经快七天了。':.8},
'B06':{'继续查公开的入轨发射目录。':.8,'六月三十日这一条后面，':.8,'下一次已经到了北京时间':1.}}


def build():
    sound=BASE/'声音';subinfo=read(sound/'字幕.json');aligned=read(sound/'旁白校时.json')
    records={r['id']:r for r in aligned['records']}
    parts=[np.zeros(round(.16*RATE),dtype=np.float32)];cursor=len(parts[0]);subs=[];segments=[];edits=[]
    maps={}
    for piece in subinfo['audio_pieces']:
        sid=piece['id'];r=records[sid];phr=r['phrases'];insertions=[]
        for text,extra in HOLDS[sid].items():
            idx=next(i for i,p in enumerate(phr) if p['text']==text)
            prev=phr[idx]['end'];nxt=phr[idx+1]['start']
            if nxt<prev:raise ValueError((sid,text,'overlapping word alignment'))
            insertions.append(((prev+nxt)/2,extra,text))
        insertions.sort()
        sr,audio=wavfile.read(sound/f'{sid}_匹配开场音量_48k_mono_float.wav');assert sr==RATE
        start=cursor/RATE;prev_sample=0
        for t,extra,purpose in insertions:
            cut=round(t*RATE);chunk=audio[prev_sample:cut].copy()
            # Silence-boundary 3ms ramps avoid an inserted edit click.
            n=min(round(.003*RATE),len(chunk));chunk[-n:]*=np.linspace(1,0,n)
            parts.append(chunk);cursor+=len(chunk)
            parts.append(np.zeros(round(extra*RATE),dtype=np.float32));cursor+=round(extra*RATE)
            prev_sample=cut
            edits.append({'segment':sid,'source_at':t,'added_seconds':extra,'after_phrase':purpose})
        parts.append(audio[prev_sample:]);cursor+=len(audio)-prev_sample
        end=cursor/RATE;segments.append({'id':sid,'title':piece['title'],'start':start,'end':end,'original_duration':len(audio)/RATE,'added_silence':sum(x[1] for x in insertions)})
        maps[sid]={'start':start,'insertions':insertions}
        for p in phr:
            onset=start+p['start']+sum(extra for at,extra,_ in insertions if at<=p['start'])
            offset=start+p['end']+sum(extra for at,extra,_ in insertions if at<p['end'])
            subs.append({'segment_id':sid,'start':onset,'end':offset,'text':p['text']})
        if sid!='B06':parts.append(np.zeros(round(.44*RATE),dtype=np.float32));cursor+=round(.44*RATE)
    duration=math.ceil(cursor/RATE*FPS)/FPS
    parts.append(np.zeros(round(duration*RATE)-cursor,dtype=np.float32))
    assembled=np.concatenate(parts);audio_path=sound/'正式旁白_48k_mono_float.wav';wavfile.write(audio_path,RATE,assembled)
    def A(sid,prefix):return q(next(s['start'] for s in subs if s['segment_id']==sid and s['text'].startswith(prefix)))
    def E(sid,prefix):return q(next(s['end'] for s in subs if s['segment_id']==sid and s['text'].startswith(prefix)))
    def S(sid):return q(next(s['start'] for s in segments if s['id']==sid))
    shots=[]
    def shot(id,a,b,kind,**kw):
        if b-a<.12:raise ValueError((id,a,b))
        shots.append({'id':id,'start':q(a),'end':q(b),'kind':kind,**kw})
    b2=S('B02');b3=S('B03');b4=S('B04');b5=S('B05');b6=S('B06')
    # B01：实际输入 → 坐标转换 → 高度尺。首次N04提交无task_id，未重复投递；本段以查证操作起手。
    shot('K01',0,A('B01','查到星历'),'sky',phase='locate')
    shot('K02',A('B01','查到星历'),A('B01','看，金星'),'sky',phase='convert')
    shot('K03',A('B01','看，金星'),b2,'sky',phase='altitude')
    # B02：方向原文 → 转身找西偏北 → 比较同一空间。
    turn=A('B02','来，转过去');west=A('B02','一个在东南')
    shot('E01',b2,turn,'evidence',asset='D2_southeast_full',label='当年报道 · 保存正文摘录',emphasis='萧山机场的东南面上空')
    shot('K04',turn,west,'sky',phase='turn')
    shot('K05',west,b3,'sky',phase='compare')
    # B03：地平面变透明；真实节点驱动时间变化，字幕说落下时正好越过地平面。
    begin_time=A('B03','把时间从八点');end_time=A('B03','这组天体')
    shot('K06',b3,begin_time,'sky',phase='below')
    points=[[begin_time,0.0],[A('B03','看这三个'),.28],[A('B03','金星还'),.68],
            [E('B03','金星还'),.86],[end_time,1.0]]
    shot('K07',begin_time,end_time,'sky',phase='time',progress_knots=[[q(t)-begin_time,p] for t,p in points])
    shot('K08',end_time,b4,'sky',phase='time',p_range=[1,1])
    # B04：一条完整原评论有自己的阅读和笑点，再用一次独立查阅镜头接新闻名字。
    punch=A('B04','坐等奥特曼');name=A('B04','俄罗斯的')
    n05_start=q(name-5.84)
    shot('C01',b4,punch,'evidence',asset='C28_full',label='天涯原评论 · ggling · 2010-07-11')
    shot('C02',punch,n05_start,'evidence',asset='C28_punchline',label='天涯原评论 · ggling · 2010-07-11',emphasis='奥特曼现身')
    shot('V05',n05_start,name,'video',source_id='N05',source_in=0,speed=1,uses=1,label='情境示意')
    shot('E02',name,b5,'evidence',asset='D2_rocket_context',label='每日商报／杭州网 · 2010-07-09 · 保存正文摘录')
    # B05：先发现6/30新疆，再核对NASA；时区表盘和真实翻页接管讲解。
    focus=A('B05','这段前面');guess=A('B05','那个飞船');nasa=A('B05','再找美国');tz=A('B05','先别被时区');flip=A('B05','再把日历');event=A('B05','七月七日')
    shot('E03',b5,focus,'evidence',asset='D2_rocket_full',label='保存新闻正文 · 完整相关段落')
    shot('E04',focus,guess,'evidence',asset='D2_rocket_xinjiang',label='前文：6月30日，新疆的另一则传闻',emphasis='就在几天前，6月30日，新疆地区也传闻出现类似不明飞行物')
    shot('E05',guess,nasa,'evidence',asset='D2_rocket_guess',label='新闻转引网友说法 · 未取得该网友原帖')
    shot('E06',nasa,tz,'evidence',asset='NASA_context',label='NASA · 2010-07-01文章 · 2016网页归档')
    lock_time=A('B05','晚上十一点')-.12
    shot('D01',tz,flip,'date',phase='timezone',progress_knots=[[0,0],[lock_time-tz,.78],[flip-tz,1]])
    shot('D02',flip,event,'date',phase='to_event')
    shot('D03',event,b6,'date',phase='event')
    # B06：相邻原始记录 → 继续翻到7/11 → 三日期同桌对照 → 下一类证据。
    next_launch=A('B06','下一次已经');in_between=A('B06','七月七日晚');recap=A('B06','查到这里');date_recap=A('B06','这次发射的');n06=q(duration-5.84)
    shot('E07',b6,next_launch,'evidence',asset='GCAT_rows',label='GCAT公开入轨发射目录 · 本地原表阅读 · UTC')
    show_next=A('B06','七月十一日')-.16
    shot('D04',next_launch,in_between,'date',phase='to_next',progress_knots=[[0,0],[show_next-next_launch,1],[in_between-next_launch,1]])
    shot('D05',in_between,recap,'date',phase='gap')
    shot('K09',recap,date_recap,'sky',phase='time',p_range=[1,1])
    shot('D06',date_recap,n06,'date',phase='gap',p_range=[1,1])
    shot('V06',n06,duration,'video',source_id='N06',source_in=0,speed=1,uses=1,label='情境示意')
    for prev,nxt in zip(shots,shots[1:]):assert abs(prev['end']-nxt['start'])<.001,(prev,nxt)
    assert shots[0]['start']==0 and shots[-1]['end']==duration
    for sub in subs:sub['start']=round(sub['start'],4);sub['end']=round(sub['end'],4)
    timeline={'duration':duration,'fps':FPS,'width':1920,'height':1080,'audio':str(audio_path),
              'voice_detection_stem':str(audio_path),'audio_pieces':segments,'subtitles':subs,'shots':shots,
              'reading_pauses':edits,'chapters':[{'title':s['title'],'start':q(s['start']),'end':q(s['end'])} for s in segments],
              'new_video_uses':{'N05':1,'N06':1},'N04':'submission connection reset without task ID; unused, fee reserved; no resubmission',
              'astro_motion':'linear interpolation between stored JPL nodes for animation only',
              'scope_end':'照片线索入口；下一环等用户反馈',
              'status':'voice_timed_action_edit'}
    write(BASE/'timeline.json',timeline)
    print(json.dumps({'duration':duration,'shots':len(shots),'subtitles':len(subs),'reading_silence_added':sum(e['added_seconds'] for e in edits),'chapters':timeline['chapters']},ensure_ascii=False))


if __name__=='__main__':build()
