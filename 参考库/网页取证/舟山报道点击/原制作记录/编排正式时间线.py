"""把实际语音词时间编排到固定证据画面与单次动作中；不变速、不循环AI视频。"""
from __future__ import annotations
import importlib.util
import math
from pathlib import Path
import numpy as np
from scipy.io import wavfile

BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('voice_local',BASE/'工具/整理正式旁白.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
read,write,sha=v.read,v.write,v.sha
SR,FPS=48000,25
VIDEO_DURATION=5.84
VIDEO_USE={'N10':3.20,'N13':5.84,'N14':5.28}
def q(t):return round(t*FPS)/FPS
def up(t):return math.ceil(t*FPS-1e-7)/FPS

def main():
    index=read(BASE/'声音/短语索引.json');assert not index['missing'],index['missing']
    plan=read(BASE/'声画执行稿.json')
    records={r['id']:r for r in index['records']}
    sources={};raw_sources={};segments=[];subtitles=[];pieces=[];cursor=0
    # 只在真正句间的无声处加空白，句内原样保留。
    for s in plan['segments']:
        sid=s['id'];r=records[sid];phrases=r['unmerged_phrases']
        wav=BASE/r['leveled_wav'];rate,data=wavfile.read(wav);assert rate==SR and data.ndim==1
        sources[sid]=data;raw_sources[sid]=v.v.decode(BASE/r['audio'])
        duration=len(data)/SR;lead=.24;tail=.72;pauses=[]
        def insert_after(pi,extra):
            if extra<=0:return
            end=phrases[pi]['end'];nxt=phrases[pi+1]['start'] if pi+1<len(phrases) else duration
            assert nxt>=end-.002,(sid,pi,'跨词不能插停顿')
            at=round((end+max(end,nxt))/2,6)
            pauses.append((at,up(extra)))
        if sid=='P10':
            # 新来访动作完整一次；真实日期出现时切回报告/日历。
            insert_after(0,max(0,VIDEO_USE['N10']+.40-lead-phrases[1]['start']))
        if sid=='P12':
            # 查阅动作从反问开始，完成后再打开真实新闻页面。
            insert_after(7,max(0,VIDEO_DURATION+.24-(phrases[8]['start']-phrases[6]['start'])))
            tail=.92
        if sid=='P14':insert_after(7,.40)
        if sid=='P16B':
            # 用户已确认的10秒样片使用原有语速/段内停顿。
            lead=.36;tail=.64
        if sid=='P16C':insert_after(3,.44);insert_after(12,.36);tail=.84
        if sid=='P16D':insert_after(2,.36)
        if sid=='P16G':insert_after(4,.32)
        if sid=='P17':tail=1.08
        pauses.sort()
        def mapped(t,edge='start'):
            return cursor+lead+t+sum(g for at,g in pauses if at<t-1e-7 or (edge=='start' and abs(at-t)<1e-7))
        length=up(lead+duration+sum(g for _,g in pauses)+tail)
        segment={'id':sid,'title':s['title'],'start':cursor,'end':round(cursor+length,6),
            'audio':r['leveled_wav'],'raw_audio':r['audio'],'raw_duration':duration,'voice_offset':lead,
            'inserted_pauses':[[at,g] for at,g in pauses],'phrases':[],'unmerged_phrases':[]}
        last=0
        for end,_ in pauses+[(duration,0)]:
            pieces.append({'id':sid,'source_in':last,'source_out':end,'start':round(mapped(last),6),'end':round(mapped(last)+end-last,6)})
            last=end
        for pi,p in enumerate(r['phrases']):
            entry={'segment':sid,'phrase_index':pi,'start':round(mapped(p['start']),4),'end':round(mapped(p['end'],'end'),4),'text':p['text']}
            assert entry['end']>entry['start'];segment['phrases'].append(entry);subtitles.append(entry)
        for pi,p in enumerate(phrases):
            segment['unmerged_phrases'].append({'segment':sid,'phrase_index':pi,'start':round(mapped(p['start']),4),
                'end':round(mapped(p['end'],'end'),4),'text':p['text']})
        segments.append(segment);cursor=round(cursor+length,6)
    S={s['id']:s for s in segments}
    def cue(sid,pi,edge='start'):return q(S[sid]['unmerged_phrases'][pi][edge])
    shots=[]
    def add(sid,ident,start,end,kind,asset,**kwargs):
        start=q(start);end=q(end);assert end>start,(sid,ident,start,end)
        shots.append({'id':ident,'segment':sid,'start':start,'end':end,'duration':round(end-start,6),'kind':kind,'asset':asset,**kwargs})
    def ev(sid,ident,a,b,asset):add(sid,ident,a,b,'evidence',asset)
    def anim(sid,ident,a,b,asset,phase,knots=None):
        add(sid,ident,a,b,'animation',asset,phase=phase,progress_knots=knots or [[0,0],[max(.04,b-a-.52),1],[b-a,1]])
    def video(sid,ident,a,source,label):
        add(sid,ident,a,a+VIDEO_USE[source],'video',source,source_id=source,source_in=0,speed=1,
            label=label,requested_duration=6,actual_source_duration=5.875,source_frames=141,source_fps=24,loop=False)
    s=S['P10'];a,b=s['start'],s['end'];date=cue('P10',1);sh=cue('P10',3)
    video('P10','S01',a,'N10','查阅与走访情境示意 · 非当年现场')
    ev('P10','S02',a+VIDEO_USE['N10'],date,'V01')
    anim('P10','S03a',date,sh,'A01','visit14')
    flip_end=min(sh+.56,cue('P10',4)-.2)
    anim('P10','S03b',sh,flip_end,'A01','visit_flip',[[0,0],[.40,1],[q(flip_end-sh),1]])
    anim('P10','S03c',flip_end,cue('P10',4),'A01','visit15')
    ev('P10','S03d',cue('P10',4),cue('P10',6),'V02_visit')
    ev('P10','S04',cue('P10',6),cue('P10',10),'V02')
    ev('P10','S05',cue('P10',10),b,'V03')
    s=S['P12'];a,b=s['start'],s['end'];turn=cue('P12',6)
    ev('P12','S06',a,cue('P12',2),'V04')
    add('P12','S07',cue('P12',2),turn,'comment','MIL11')
    video('P12','S08',turn,'N13','查阅动作情境示意 · 原文随后展示')
    add('P12','S09',turn+VIDEO_DURATION,b,'local_action','open_M01')
    s=S['P13'];a,b=s['start'],s['end']
    ev('P13','S10',a,cue('P13',2),'M01_title')
    ev('P13','S11',cue('P13',2),cue('P13',7),'M01_body')
    anim('P13','S12',cue('P13',7),b,'A02a','notice_range')
    s=S['P13B'];a,b=s['start'],s['end']
    ev('P13B','S13',a,cue('P13B',3),'BBC_title')
    ev('P13B','S14',cue('P13B',3),cue('P13B',7),'BBC_dates')
    ev('P13B','S15',cue('P13B',7),b,'BBC_notice')
    s=S['P14'];a,b=s['start'],s['end']
    ev('P14','S16',a,cue('P14',2),'M02_title')
    ev('P14','S17',cue('P14',2),cue('P14',4),'M02_body')
    anim('P14','S18',cue('P14',4),b,'A02b','separate_times',
        [[0,0],[cue('P14',6)-cue('P14',4),.5],[cue('P14',7,'end')-cue('P14',4),1],[b-cue('P14',4),1]])
    s=S['P15'];a,b=s['start'],s['end']
    ev('P15','S19',a,cue('P15',3),'E04_title')
    ev('P15','S20',cue('P15',3),cue('P15',6),'E04_quote')
    add('P15','S21',cue('P15',6),cue('P15',11),'local_action','anonymous_gap')
    ev('P15','S22',cue('P15',11),b,'E04_context')
    s=S['P16A'];a,b=s['start'],s['end']
    video('P16A','S23',a,'N14','阅读报纸情境示意 · 非当年目击者')
    add('P16A','S24',a+VIDEO_USE['N14'],b,'comment','L01_news',source_id='L01',base_fixed=True)
    for sid,ident,asset,source_id in [('P16B','S26','L02','L02'),('P16C','S27','L04_roles','L04_full'),
        ('P16D','S30','L05','L05'),('P16E','S31','L07','L07'),('P16F','S32','OTH04','OTH04'),('P16G','S33','OTH09','OTH09')]:
        s=S[sid];add(sid,ident,s['start'],s['end'],'comment',asset,source_id=source_id,base_fixed=True)
    s=S['P16H'];add('P16H','S34',s['start'],s['end'],'local_action','A03_return')
    s=S['P17'];a,b=s['start'],s['end']
    ev('P17','S35',a,cue('P17',3),'airport_report')
    ev('P17','S36',cue('P17',3),cue('P17',4),'E04_quote')
    add('P17','S37',cue('P17',4),b,'local_action','keep_open')

    # 每一条红线只在实际口播对应原句时开始；原页的多个重点累计保留。
    cue_spec=[
        ('P16A','L01_news',0,5,5),('P16A','L01_unseen',0,7,7),
        ('P16B','L02',0,1,1),('P16B','L02',1,2,2),('P16B','L02',2,3,3),
        ('P16C','L04_roles',0,2,2),('P16C','L04_intro',0,8,8),('P16C','L04_intro',1,9,10),
        ('P16C','L04_account',0,11,11),('P16C','L04_account',1,12,12),
        ('P16D','L05',0,2,2),('P16E','L07',0,2,3),('P16E','L07',1,5,5),
        ('P16F','OTH04',0,3,3),('P16F','OTH04',1,4,4),
        ('P16G','OTH09',1,1,2),('P16G','OTH09',0,4,4),
    ]
    underlines=[]
    for sid,asset,group_index,p0,p1 in cue_spec:
        definition=plan['comment_dynamic_underlines'][asset];g=definition['underline_groups'][group_index]
        start=S[sid]['unmerged_phrases'][p0]['start'];speech_end=S[sid]['unmerged_phrases'][p1]['end']
        duration=min(.8,max(.36,(speech_end-start)*.6))
        shot=next(s for s in shots if s['segment']==sid and s['kind']=='comment')
        assert start>=shot['start'] and start+duration<shot['end'],(sid,start,shot)
        item={'key':g['key'],'segment':sid,'asset':asset,'display_asset':shot['asset'],'source_id':definition['source_id'],
            'quote':g['quote'],'spoken_text':''.join(p['text'] for p in S[sid]['unmerged_phrases'][p0:p1+1]),
            'start':round(start,4),'end':round(start+duration,4),'speech_end':round(speech_end,4),
            'draw_duration':round(duration,4),'hold_until':shot['end'],'segments':g['segments'],
            'width_px':g.get('width_px',5),'color_rgb':g.get('color_rgb',[215,42,48]),
            'timing_method':'actual_ASR_word_bounds','underline_baked_into_source':False}
        underlines.append(item)
        shot.setdefault('underline_cues',[]).append(item)
    underlines.sort(key=lambda c:c['start'])
    for shot in shots:
        if 'underline_cues' in shot:shot['underline_cues'].sort(key=lambda c:c['start'])
    voice=np.zeros(round(cursor*SR),np.float32);detector=np.zeros_like(voice)
    for p in pieces:
        i,j=round(p['source_in']*SR),round(p['source_out']*SR);k=round(p['start']*SR)
        chunk=sources[p['id']][i:j].copy();raw=raw_sources[p['id']][i:j].copy()
        if p['source_in']>0:
            chunk[:96]*=np.linspace(0,1,96,dtype=np.float32);raw[:96]*=np.linspace(0,1,96,dtype=np.float32)
        if p['source_out']<len(sources[p['id']])/SR:
            chunk[-96:]*=np.linspace(1,0,96,dtype=np.float32);raw[-96:]*=np.linspace(1,0,96,dtype=np.float32)
        voice[k:k+len(chunk)]+=chunk;detector[k:k+len(raw)]+=raw
    cache=BASE/'缓存';cache.mkdir(exist_ok=True)
    voice_path=cache/'调查后续_旁白原声_48k_mono_float.wav'
    detector_path=cache/'调查后续_检测旁白_48k_mono_float.wav'
    wavfile.write(voice_path,SR,voice);wavfile.write(detector_path,SR,detector)
    assert max(abs(voice))<.99
    for x,y in zip(shots,shots[1:]):assert abs(x['end']-y['start'])<1e-5,(x,y)
    assert abs(shots[-1]['end']-cursor)<1e-5
    for x,y in zip(subtitles,subtitles[1:]):assert x['end']<=y['start']+.001,(x,y)
    timeline={'version':1,'status':'ready_for_local_render','duration':cursor,'fps':FPS,'width':1920,'height':1080,
        'audio':str(voice_path.relative_to(BASE)),'narration_mono':str(voice_path.relative_to(BASE)),
        'detector_mono':str(detector_path.relative_to(BASE)),'segments':segments,'shots':shots,'subtitles':subtitles,
        'audio_pieces':pieces,'underline_cues':underlines,'evidence_assets':plan['evidence_assets'],
        'time_stretch':False,'ai_video_use':'三条正常速度各一次：N10 3.20秒、N13 5.84秒、N14 5.28秒；请求6秒、返回5.875秒141帧24fps；不循环、不末帧填长、不为用满素材空等',
        'evidence_motion':'评论原页完全固定，旁白讲到原话才从左到右动态画线；同评论各重点累计保留',
        'script_sha256':sha(BASE/'声画执行稿.json'),'audio_index_sha256':sha(BASE/'声音/短语索引.json'),
        'audio_peak_dbfs':v.v.db(max(abs(voice))),'human_listening_claimed':False}
    # 独立视觉修订仅在真实新素材通过目视且显式启用后接入；不改语音时码。
    from 接入巨物对照 import apply_if_enabled
    timeline=apply_if_enabled(timeline)
    shots=timeline['shots']
    write(BASE/'timeline.json',timeline)
    export=BASE/'导出';export.mkdir(exist_ok=True)
    srt=[]
    for i,p in enumerate(subtitles,1):
        srt.append(f"{i}\n{v.v.srt_time(p['start'])} --> {v.v.srt_time(p['end'])}\n{p['text']}\n")
    (export/'调查后续_旁白字幕.srt').write_text('\n'.join(srt),encoding='utf-8')
    def ass_time(t):
        cs=round(t*100);h,cs=divmod(cs,360000);m,cs=divmod(cs,6000);s,cs=divmod(cs,100)
        return f'{h}:{m:02d}:{s:02d}.{cs:02d}'
    ass='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,46,&H00FFFFFF,&H00FFFFFF,&H00151515,&H78000000,0,0,0,0,100,100,0,0,1,3,0,2,70,70,42,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    for p in subtitles:
        text=p['text'].rstrip('，。？！：；')
        ass+=f"Dialogue: 0,{ass_time(p['start'])},{ass_time(p['end'])},Default,,0,0,0,,{text}\n"
    (export/'调查后续_字幕.ass').write_text(ass,encoding='utf-8-sig')
    report={'status':'passed','duration':cursor,'frames':round(cursor*FPS),'voice_samples':len(voice),
        'segments':len(segments),'shots':len(shots),'subtitles':len(subtitles),'dynamic_underlines':len(underlines),
        'fixed_complete_comment_shots':7,'ai_ids':[s['source_id'] for s in shots if s['kind']=='video'],
        'ai_durations':{s['source_id']:round(s['end']-s['start'],6) for s in shots if s['kind']=='video'},'audio_source_unchanged':True,'time_stretch':False,
        'voice_peak_dbfs':v.v.db(max(abs(voice))),'word_timing_method':'actual_ASR_word_bounds',
        'subtitle_order_no_overlap':True,'shots_cover_whole_duration':True,'paid_api_calls':0,
        'segments_timing':[{k:s[k] for k in ['id','start','end','raw_duration','inserted_pauses']} for s in segments]}
    write(BASE/'声音/正式时间线核验.json',report)
    print(__import__('json').dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
