"""Compile explicit editorial decisions against the actual narration ledger.
This does not invent a story or infer a visual from keywords. It catches stale
timing, footage looping, missing source files and unmotivated scene placeholders.
"""
from pathlib import Path
import argparse, hashlib, json, math, os, re, copy

ROOT=Path(__file__).resolve().parents[2]

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def need(ok,msg):
    if not ok:raise ValueError(msg)
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def compile_plan(plan_path,out):
    plan_path=Path(plan_path).resolve();base=plan_path.parent;out=Path(out).resolve();p=read(plan_path)
    timeline_path=(base/p['timeline']).resolve();t=read(timeline_path)
    need(sha(timeline_path)==p['timeline_sha256'],'实音时间线已改变；重新决定剪点，不能继续用旧分镜秒数')
    cue_map={};cue_digest=None
    if p.get('visual_cues'):
        cue_path=(base/p['visual_cues']).resolve();cue_data=read(cue_path);cue_digest=sha(cue_path)
        need(cue_data.get('timeline_sha256')==sha(timeline_path),'动画触发点仍绑定旧时间线')
        narration=(base/p['narration']).resolve()
        need(cue_data.get('narration_sha256')==sha(narration),'动画触发点仍绑定旧旁白PCM')
        cue_map={c['id']:c for c in cue_data['cues']}
        need(len(cue_map)==len(cue_data['cues']),'动画触发点ID重复')
    fps=t['fps'];need(type(fps) is int and 1<=fps<=60,'fps必须为有效整数')
    need(p.get('shots'),'分镜为空；先完成逐镜导演决定')
    segments={s['id']:s for s in t['segments']};cursor=0;ids=set();shots=[];reviews=[];uses={}
    need(len(segments)==len(t['segments']),'实音段ID重复')
    for s in p['shots']:
        sid=s['id'];need(re.fullmatch(r'[A-Za-z0-9_-]+',sid) is not None and sid not in ids,'无效或重复镜头ID: '+sid);ids.add(sid)
        need(s.get('viewer_task','').strip(),'缺少观众在此镜需要看什么: '+sid)
        need(s.get('transition_reason','').strip(),'缺少为什么切到此镜: '+sid)
        seg=segments[s['paragraph_id']]
        a=float(s.get('start_offset',0));b=s.get('end_offset','segment_end')
        b=seg['end']-seg['start'] if b=='segment_end' else float(b)
        need(math.isfinite(a) and math.isfinite(b) and 0<=a<b<=seg['end']-seg['start']+1e-7,'镜头越过所属实音段: '+sid)
        start=(seg['start']+a)*fps;end=(seg['start']+b)*fps
        need(abs(start-round(start))<1e-5 and abs(end-round(end))<1e-5,'剪点必须对齐视频帧: '+sid)
        start,end=round(start),round(end);need(start==cursor,'镜头空洞或重叠: '+sid)
        asset=(base/s['path']).resolve();need(asset.is_file(),'素材不存在: '+sid)
        h=sha(asset);need(s.get('asset_sha256')==h,'素材换版但分镜未重新核对: '+sid)
        kind=s['kind'];need(kind in ('image','video','animation','ai'),'未知素材类型: '+sid)
        need(s.get('speed',1)==1 and not s.get('loop',False),'不允许用循环或变速补镜头: '+sid)
        if kind=='ai':
            need(h not in uses,'同一AI视频重复使用: '+sid)
            need(s.get('native_label') is True,'AI情境说明须在采用素材中确认一次: '+sid)
            need(s.get('acceptance_record'),'AI下载不等于采用，缺少实际画面验收记录: '+sid)
        if kind!='image':
            import av
            with av.open(str(asset)) as c:
                st=c.streams.video[0];duration=float(st.duration*st.time_base)
            src_in=float(s.get('in',0));need(math.isfinite(src_in) and src_in>=0,'无效源入点: '+sid)
            need(src_in+(end-start)/fps<=duration+1e-6,'视频不足，禁止静帧/循环补齐: '+sid)
        uses[h]=sid
        keep=('native_label','source_note','source_note_safe_area','layout','watermark_position','subtitle_style','in')
        shot={'id':sid,'path':os.path.relpath(asset,out.parent),'kind':kind,'duration':(end-start)/fps,'expected_sha256':h}
        shot.update({k:s[k] for k in keep if k in s});shots.append(shot)
        review={'id':sid,'paragraph_id':s['paragraph_id'],'start':start/fps,'end':end/fps,
                'viewer_task':s['viewer_task'],'transition_reason':s['transition_reason'],
                'source_ids':s.get('source_ids',[]),'asset_sha256':h,'acceptance_record':s.get('acceptance_record'),
                'manual_review_required':['动作/旁白意义一致','来源及限定词可读','字幕/水印不遮关键内容','无任务空等与章间衔接']}
        if s.get('cue_ids'):
            need(cue_digest is not None,'镜头有动画触发点但没有绑定visual_cues: '+sid)
            cues=[]
            for cid in s['cue_ids']:
                need(cid in cue_map,'动画触发点缺失: '+cid)
                cue=cue_map[cid];at=float(cue.get('time',cue.get('start',-1)))
                need(start/fps<=at<end/fps,'触发点不在当前镜头，停顿修改后需重排: '+cid)
                cues.append(cue)
            receipt=read((base/s['cue_render_receipt']).resolve())
            need(receipt.get('asset_sha256')==h and receipt.get('visual_cues_sha256')==cue_digest,'动画成片尚未用当前触发点重渲染: '+sid)
            need(set(s['cue_ids']).issubset(set(receipt.get('cue_ids',[]))),'动画回执未包含所需触发点: '+sid)
            review['visual_cues']=cues
        if s.get('acceptance_record'):
            receipt=(base/s['acceptance_record']).resolve();need(receipt.is_file(),'验收记录丢失: '+sid)
            record=read(receipt);need(record.get('asset_sha256')==h,'验收记录不是当前素材: '+sid)
            need(record.get('status')=='accepted','素材尚未通过实际画面验收: '+sid)
            review['acceptance_record_sha256']=sha(receipt)
        reviews.append(review);cursor=end
    need(cursor==t['frames'],'镜头没有完整覆盖实音时间线')
    audio=(base/p['audio']).resolve();need(audio.is_file() and sha(audio)==p['audio_sha256'],'混音换版未同步')
    settings=copy.deepcopy(p.get('delivery',{}));logo=(ROOT/'默认配置/工作室.json');brand=read(logo)['brand']
    def rebase_mark(obj,key):
        if obj.get(key):
            path=(base/obj[key]).resolve();need(path.is_file(),'自定义水印文件不存在: '+str(path))
            obj[key]=os.path.relpath(path,out.parent)
    rebase_mark(settings.get('watermark',{}),'path')
    for version in settings.get('versions',[]):
        rebase_mark(version,'watermark_path');rebase_mark(version.get('watermark_override',{}),'path')
    width,height=settings.get('width',1920),settings.get('height',1080)
    mark_width=max(1,round(224*width/1920))
    default_mark={'path':os.path.relpath(ROOT/brand['bili_watermark'],out.parent),'width':mark_width,
        'x':width-mark_width-round(32*width/1920),'y':round(40*height/1080)}
    m={'schema_version':1,'title':p['title'],'width':settings.get('width',1920),'height':settings.get('height',1080),'fps':fps,
       'output_dir':p.get('output_dir','导出'),'shots':shots,'audio':{'path':os.path.relpath(audio,out.parent),'expected_sha256':sha(audio)},
       'subtitles':[{k:v for k,v in q.items() if k in ('start','end','text','style')} for q in t['subtitles']],
       'chapters':[{'start':c['start'],'title':c['title']} for c in t['chapters']],
       'subtitle_style':settings.get('subtitle_style',{'profile':'main'}),
       'watermark':settings.get('watermark',default_mark),
       'versions':settings.get('versions',[{'id':'bili','label':'B站水印版','watermark':True},{'id':'clean','label':'无个人水印版','watermark':False}])}
    m['editorial_binding']={'plan_path':os.path.relpath(plan_path,out.parent),'plan_sha256':sha(plan_path),
        'timeline_path':os.path.relpath(timeline_path,out.parent),'timeline_sha256':sha(timeline_path)}
    if cue_digest:
        m['editorial_binding'].update(visual_cues_path=os.path.relpath(cue_path,out.parent),visual_cues_sha256=cue_digest,
            narration_path=os.path.relpath(narration,out.parent),narration_sha256=sha(narration))
    save(out,m);save(out.with_name(out.stem+'_导演核对.json'),{'status':'timing_and_assets_bound_visual_review_still_required',
        'plan_sha256':sha(plan_path),'timeline_sha256':sha(timeline_path),'manifest_sha256':sha(out),'shots':reviews,'frames':cursor,
        'visual_cues_sha256':cue_digest,'semantic_review':'viewing tasks are written editorial decisions, not automated aesthetic approval','paid_calls':0})
    print(json.dumps({'manifest':str(out),'shots':len(shots),'frames':cursor,'duration':cursor/fps},ensure_ascii=False))
    return m

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args();compile_plan(a.plan,a.output)
