"""Real word timestamp alignment + approved voice level matching, offline only."""
from pathlib import Path
from difflib import SequenceMatcher
import argparse,hashlib,json,re,subprocess
import numpy as np
from scipy import ndimage,signal
from scipy.io import wavfile
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[2]
RATE=48000
FF=imageio_ffmpeg.get_ffmpeg_exe()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def db(v):return float(20*np.log10(max(float(v),1e-12)))
def number_zh(match):
    s=match.group()
    digits='〇一二三四五六七八九'
    if len(s)==4 or len(s)>4:return ''.join(digits[int(c)] for c in s)
    n=int(s)
    if n<10:return digits[n]
    tens,unit=divmod(n,10)
    return (digits[tens] if tens>1 else '')+'十'+(digits[unit] if unit else '')

def norm(value):
    value=re.sub(r'(\d+)\.(\d+)',lambda m:number_zh(re.match(r'\d+',m.group(1)))+'点'+''.join('〇一二三四五六七八九'[int(c)] for c in m.group(2)),value)
    value=re.sub(r'\d+',number_zh,value)
    value=value.translate(str.maketrans({'零':'〇','裡':'里','這':'这','個':'个','時':'时','後':'后','來':'来','說':'说','為':'为','發':'发','裡':'里','還':'还','號':'号','體':'体','們':'们','錄':'录','飛':'飞','國':'国','點':'点','經':'经','緯':'纬','間':'间','過':'过','劃':'划','圖':'图','誰':'谁','傳':'传','聲':'声','見':'见','對':'对','東':'东','陽':'阳','邊':'边','頭':'头','嗎':'吗','運':'运','進':'进','貨':'货','與':'与','請':'请','認':'认','領':'领','區':'区','場':'场','換':'换','從':'从','則':'则','幾':'几','萬':'万','實':'实','數':'数','據':'据','確':'确','將':'将','無':'无'}))
    return ''.join(c.lower() for c in value if c.isalnum() or c=='〇')

def decode(path,rate=RATE):
    res=subprocess.run([FF,'-v','error','-i',str(path),'-vn','-f','f32le','-ar',str(rate),'-ac','1','pipe:1'],capture_output=True,check=True)
    return np.frombuffer(res.stdout,dtype='<f4').copy()

def align(reference,asr,phrases):
    assert ''.join(phrases)==reference,'Phrase text must match current plan exactly'
    words=[w for s in asr['segments'] for w in s['words'] if norm(w['word'])]
    observed=''
    char_words=[]
    for wi,w in enumerate(words):
        token=norm(w['word'])
        if re.search(r'\d+\.$',w['word'].strip()) and wi+1<len(words) and re.match(r'^\d',words[wi+1]['word'].strip()):
            # Whisper can split decimal 1.1 into actual words "1." and "1".
            # Preserve the spoken decimal point on the first word's bounds.
            token+='点'
        observed+=token
        char_words.extend([wi]*len(token))
    expected=norm(reference)
    mapping=[None]*len(expected)
    differences=[]
    matcher=SequenceMatcher(None,expected,observed,autojunk=False)
    for tag,a,b,c,d in matcher.get_opcodes():
        if tag=='equal':
            for ri,oi in zip(range(a,b),range(c,d)):mapping[ri]=[char_words[oi]]
        else:
            indices=sorted(set(char_words[c:d]))
            detail={'operation':tag,'reference':expected[a:b],'asr':observed[c:d],
                    'reference_range':[a,b],'asr_range':[c,d],
                    'time_start':words[indices[0]]['start'] if indices else None,
                    'time_end':words[indices[-1]]['end'] if indices else None,
                    'classification':'ASR_difference_not_proof_of_TTS_error'}
            differences.append(detail)
            if tag=='replace' and indices:
                if b-a==d-c:
                    # Equal-length substitutions keep their actual observed
                    # word bounds, e.g. 帖正 -> 铁证 across two sentences.
                    # This pairs alignment positions, not proportional times.
                    for ri,oi in zip(range(a,b),range(c,d)):mapping[ri]=[char_words[oi]]
                else:
                    # Unknown length mismatch retains the observed span; no
                    # fabricated character-time interpolation is introduced.
                    for ri in range(a,b):mapping[ri]=indices
    offsets=[]
    cursor=0
    for p in phrases:
        n=len(norm(p));offsets.append((cursor,cursor+n));cursor+=n
    aligned=[]
    issues=[]
    for pi,(phrase,(a,b)) in enumerate(zip(phrases,offsets)):
        indices=sorted({w for m in mapping[a:b] if m for w in m})
        missing=sum(m is None for m in mapping[a:b])
        if not indices:
            issues.append({'phrase_index':pi,'text':phrase,'severity':'unmatched_phrase','reason':'No actual ASR word matches; no timing fabricated.'})
            aligned.append({'text':phrase,'start':None,'end':None,'matched':False})
            continue
        lo,hi=words[indices[0]]['start'],words[indices[-1]]['end']
        entry={'text':phrase,'start':round(lo,4),'end':round(hi,4),'matched':True,'word_indices':indices,'original_phrase_indices':[pi],
            'alignment_method':'original_text_sequence_match_to_actual_ASR_word_bounds',
            'unmatched_reference_chars':missing,'reference_chars':b-a}
        if missing:
            issues.append({'phrase_index':pi,'text':phrase,'severity':'review_missing_ASR_characters','count':missing})
        if hi<=lo:
            issues.append({'phrase_index':pi,'text':phrase,'severity':'zero_duration_word_boundary'})
        aligned.append(entry)
    # A Chinese word may straddle the manually chosen subtitle boundary. Merge
    # only that pair instead of dividing a word's duration by character count.
    merged=[]
    for item in aligned:
        if merged and item['start'] is not None and merged[-1]['end'] is not None and item['start']<merged[-1]['end']-0.001:
            prev=merged[-1]
            prev['text']+=item['text']
            prev['end']=max(prev['end'],item['end'])
            prev['word_indices']=sorted(set(prev['word_indices']+item['word_indices']))
            prev['original_phrase_indices']+=item['original_phrase_indices']
            prev['unmatched_reference_chars']+=item['unmatched_reference_chars']
            prev['reference_chars']+=item['reference_chars']
            prev['boundary_merge']='Merged because actual ASR token crossed subtitle boundary; no fabricated per-character timing.'
        else:merged.append(item.copy())
    first_mapped=next((i for i,m in enumerate(mapping) if m),None)
    last_mapped=next((i for i in range(len(mapping)-1,-1,-1) if mapping[i]),None)
    coverage=sum(m is not None for m in mapping)/max(1,len(mapping))
    exact=sum(b-a for tag,a,b,c,d in matcher.get_opcodes() if tag=='equal')/max(1,len(expected))
    for index,item in enumerate(merged):item['phrase_index']=index
    return {'reference':reference,'normalized_reference':expected,'asr_text':asr['asr_text'],
        'normalized_asr':observed,'sequence_similarity':matcher.ratio(),'exact_reference_match_fraction':exact,
        'matched_reference_fraction':coverage,'differences':differences,'phrases':merged,'unmerged_phrases':aligned,'issues':issues,
        'head_reference_unmatched':first_mapped!=0,'tail_reference_unmatched':last_mapped!=len(expected)-1,
        'asr_words':words,'method':'Phrase boundaries use matched actual word timestamps. No entire-clip duration allocation or per-character duration interpolation.',
        'judgment_limit':'ASR differences and timestamps require review; homophones alone do not prove spoken error. This is not a claim of human listening.'}

def voiced_median(audio,detector=None):
    detector=audio if detector is None else detector
    vals=[]
    for i in range(0,min(len(audio),len(detector))-12000,12000):
        level=float(np.sqrt(np.mean(detector[i:i+12000]**2)))
        if level>.018:vals.append(float(np.sqrt(np.mean(audio[i:i+12000]**2))))
    if not vals:raise RuntimeError('No voiced analysis windows')
    return float(np.median(vals))

def match_level(audio,target):
    before=voiced_median(audio)
    gain=target/before
    raised=audio*gain
    peak=ndimage.maximum_filter1d(np.abs(raised),size=961,mode='nearest')
    cap=np.minimum(1,.82/np.maximum(peak,1e-8))
    cap=ndimage.minimum_filter1d(cap,size=2401,mode='nearest')
    cap=np.minimum(cap,signal.savgol_filter(cap,481,1))
    out=(raised*cap).astype(np.float32)
    return out,{'linear_gain':gain,'gain_db':db(gain),'raw_peak_dbfs':db(np.max(np.abs(audio))),
        'raw_voiced_median_dbfs':db(before),'reference_voiced_median_dbfs':db(target),
        'processed_voiced_median_dbfs':db(voiced_median(out,audio)),
        'processed_peak_dbfs':db(np.max(np.abs(out))),
        'limiter_max_reduction_db':db(np.min(cap)),'fraction_limited':float(np.mean(cap<.99)),
        'limiter_method':'same 20ms peak lookahead / 50ms protection / 10ms smoothing as accepted opening',
        'time_stretch':False}

def srt_time(t):
    ms=round(t*1000);hh,ms=divmod(ms,3600000);mm,ms=divmod(ms,60000);ss,ms=divmod(ms,1000)
    return f'{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}'
ORIGINAL_NORM=norm
def normalise(text):
    text=re.sub(r'<#\d+(?:\.\d+)?#>','',text)
    text=re.sub(r'(?<!\d)\d{3}(?!\d)',lambda m:''.join('〇一二三四五六七八九'[int(c)] for c in m.group()),text)
    return ORIGINAL_NORM(text)
norm=normalise
def convert_provider(data):
    if isinstance(data,dict):data=data.get('subtitles') or data.get('subtitle') or data.get('data')
    assert isinstance(data,list),'Unexpected provider subtitle schema'
    segments=[]
    for item in data:
        words=[]
        for w in item.get('timestamped_words',[]):
            if not normalise(w['word']):continue
            token=dict(word=w['word'],start=w['time_begin']/1000,end=w['time_end']/1000,
                provider_word_begin=w.get('word_begin'),provider_word_end=w.get('word_end'))
            # 发音词典的音素可能重复映射同一个原文位置，合并其真实时间覆盖。
            if words and w.get('word_begin') is not None and all(words[-1][k]==token[k] for k in ['word','provider_word_begin','provider_word_end']):
                words[-1]['start']=min(words[-1]['start'],token['start'])
                words[-1]['end']=max(words[-1]['end'],token['end'])
            else:words.append(token)
        assert words,'Provider did not return word timestamps'
        segments.append(dict(start=item['time_begin']/1000,end=item['time_end']/1000,text=item['text'],words=words))
    return dict(segments=segments,asr_text=''.join(x['text'] for x in segments))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--only',nargs='*');a=ap.parse_args()
    plan=read(a.plan);target=read(ROOT/'默认配置/声音.json')['voice_processing']['target_voiced_median']
    existing=read(a.output/'paragraphs.json') if (a.output/'paragraphs.json').exists() else []
    by={r['id']:r for r in existing};expected={r['id']:r for r in plan['paragraphs']}
    for ident,old in by.items():
        assert ident in expected and old['text']==expected[ident]['text'],'Existing paragraph manifest belongs to a different script; use a new output directory'
    rows=[]
    for row in plan['paragraphs']:
        if a.only and row['id'] not in a.only:continue
        receipt=read(a.cache/'receipts'/(row['cache_key']+'.json'));assert receipt['status']=='completed'
        raw=a.cache/receipt['audio_file'];assert sha(raw)==receipt['audio_sha256']
        assert receipt.get('provider_subtitle_file'),'Recover provider word timestamps without repeating the paid speech call'
        provider=convert_provider(read(a.cache/receipt['provider_subtitle_file']))
        aligned=align(row['tts_text'],provider,row['tts_phrases']);assert aligned['matched_reference_fraction']>=.999,aligned['differences']
        audio=decode(raw);processed,levels=match_level(audio,target);dur=len(audio)/RATE
        out=a.output/(row['id']+'_48k_mono.wav');out.parent.mkdir(parents=True,exist_ok=True);wavfile.write(out,RATE,processed)
        phrases=[]
        for p in aligned['phrases']:
            assert p['matched'] and 0<=p['start']<p['end']<=dur+.04
            ix=p['original_phrase_indices'];phrases.append({'text':''.join(row['phrases'][i] for i in ix),'tts_text':p['text'],'start':p['start'],'end':min(dur,p['end']),'time_basis':'provider_actual_word_timestamps'})
        assert ''.join(p['text'] for p in phrases)==row['text']
        result={'id':row['id'],'text':row['text'],'audio':out.name,'audio_sha256':sha(out),'duration':dur,'sample_rate':RATE,'samples':len(audio),'phrases':phrases,'level_match':levels,'time_stretch':False,'independent_asr':'not_yet_run','listening_review':'not_yet_reviewed'}
        save(a.output/(row['id']+'.json'),result);rows.append(result);by[row['id']]=result
        out.with_suffix('.srt').write_text('\n'.join(f'{i+1}\n{srt_time(p["start"])} --> {srt_time(p["end"])}\n{p["text"]}\n' for i,p in enumerate(phrases)),'utf-8')
    adopted=[by[r['id']] for r in plan['paragraphs'] if r['id'] in by]
    save(a.output/'paragraphs.json',adopted);print(json.dumps({'processed_this_run':len(rows),'adopted_paragraphs':len(adopted),'paid_calls':0},ensure_ascii=False))
if __name__=='__main__':main()
