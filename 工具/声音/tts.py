"""MiniMax paragraph TTS adapter: plan is offline; execute is explicit and budgeted.
Secrets come only from MINIMAX_API_KEY. Ambiguous submissions never auto-retry.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, math, os, re, time, unicodedata
import requests
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8');tmp.replace(p)
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def billable_characters(text):
    return sum(2 if unicodedata.name(c,'').startswith(('CJK UNIFIED IDEOGRAPH','CJK COMPATIBILITY IDEOGRAPH')) else 1 for c in text)
def make_plan(source,out,rate):
    if not math.isfinite(rate) or rate<=0:raise ValueError('Rate must be a finite positive current price estimate')
    cfg=read(ROOT/'默认配置/声音.json');data=read(source);rows=[]
    ids=set()
    for p in data['paragraphs']:
        assert re.fullmatch(r'[A-Za-z0-9_-]+',p['id']) and p['id'] not in ids
        ids.add(p['id']);formal=p['text'];spoken=p.get('tts_text',formal)
        phrases=p.get('phrases',[formal]);tts_phrases=p.get('tts_phrases',[spoken])
        assert ''.join(phrases)==formal and ''.join(tts_phrases)==spoken
        pronunciation=p.get('pronunciation_dict')
        if '啊子牙' in spoken:
            spoken=spoken.replace('啊子牙','阿子牙');tts_phrases=[v.replace('啊子牙','阿子牙') for v in tts_phrases]
            pronunciation=dict(pronunciation or {})
            tones=list(pronunciation.get('tone',[]))
            if not any(v.startswith('阿子牙/') for v in tones):tones.append('阿子牙/(a1)(zi3)(ya2)')
            pronunciation['tone']=tones
        d=cfg['tts'];request={'model':d['model'],'text':spoken,'stream':False,
            'voice_setting':{k:d[k] for k in ['voice_id','speed','vol','pitch','emotion']},
            'audio_setting':{k:d[k] for k in ['sample_rate','bitrate','format','channel']},
            'language_boost':d['language_boost'],'subtitle_enable':True,'subtitle_type':'word','output_format':'hex'}
        if pronunciation:request['pronunciation_dict']=pronunciation
        # Official 2026-10-26 rule: one Han ideograph = 2; other text characters = 1.
        bill=billable_characters(spoken)
        rows.append({'id':p['id'],'text':formal,'tts_text':spoken,'phrases':phrases,'tts_phrases':tts_phrases,
            'request':request,'cache_key':digest(request),'estimated_billable_characters':bill,'estimated_cost_cny':round(bill*rate/10000,6)})
    plan={'schema_version':1,'source_filename':Path(source).name,'source_sha256':sha(source),'created_at':now(),
        'default_voice_id':cfg['tts']['voice_id'],'rate_cny_per_10000_weighted_characters':rate,
        'price_basis':'Rate is an offline estimate. Official reference checked 2026-10-26: speech-2.8-hd 3.50 CNY per 10k weighted input characters. A new paid run must bind current price evidence and real session authorization.',
        'billing_verified':False,'paragraphs':rows,'estimated_total_cny':round(sum(r['estimated_cost_cny'] for r in rows),6),'paid_calls':0}
    save(out,plan);print(json.dumps({'plan':str(out),'paragraphs':len(rows),'estimate_cny':plan['estimated_total_cny'],'paid_calls':0},ensure_ascii=False))
def authorization_check(auth_path,plan_path,plan,rows,budget):
    if not auth_path:raise ValueError('New paid TTS needs an authorization record bound to this plan and current price evidence; reuse existing session authorization, do not invent approval')
    a=read(auth_path)
    if a.get('approved') is not True or a.get('plan_sha256')!=sha(plan_path):raise ValueError('Approval must bind the exact current plan hash')
    if not str(a.get('approval_reference','')).strip() or not str(a.get('scope','')).strip():raise ValueError('Record the real existing user instruction and its scope')
    cap=a.get('budget_cap_cny');maximum=a.get('max_new_requests')
    if not isinstance(cap,(int,float)) or not math.isfinite(cap) or cap<budget or type(maximum) is not int or maximum<0:raise ValueError('Budget/request limits do not match authorization')
    if not {r['id'] for r in rows}<=set(a.get('approved_paragraph_ids',[])):raise ValueError('Selected TTS paragraphs exceed authorization scope')
    basis=a.get('price_basis',{})
    if basis.get('verified_for_this_plan') is not True:raise ValueError('Verify price for this specific plan')
    checked=datetime.datetime.fromisoformat(basis['checked_at'].replace('Z','+00:00'))
    if checked.tzinfo is None:raise ValueError('Price check time needs timezone')
    age=(datetime.datetime.now(datetime.timezone.utc)-checked).total_seconds()
    if not -300<=age<=7*86400:raise ValueError('Price evidence is future-dated or more than seven days old; refresh before new paid synthesis')
    url=urlparse(basis.get('source_url',''))
    if url.scheme!='https' or not url.hostname:raise ValueError('Price basis needs an HTTPS source')
    evidence=Path(auth_path).resolve().parent/basis['evidence_file']
    if not evidence.is_file() or sha(evidence)!=basis.get('evidence_sha256'):raise ValueError('Price evidence missing or changed')
    if basis.get('rate_cny_per_10000_weighted_characters')!=plan.get('rate_cny_per_10000_weighted_characters'):raise ValueError('Price evidence and request plan rates differ')
    if any(r['request']['model']!=basis.get('model') for r in rows):raise ValueError('Price evidence is for a different TTS model')
    return a
def execute(plan_path,out,budget,only,retry_rejected,auth_path=None,transport=None):
    if not math.isfinite(budget) or budget<0:raise ValueError('Budget cap must be finite and nonnegative')
    plan=read(plan_path);rows=[r for r in plan['paragraphs'] if not only or r['id'] in only]
    assert rows,'No selected paragraphs'
    for row in rows:
        assert row['estimated_billable_characters']==billable_characters(row['request']['text']),'Character estimate does not match actual spoken request'
        cost=row['estimated_cost_cny']
        assert isinstance(cost,(int,float)) and math.isfinite(cost) and cost>=0,'Invalid estimated cost'
        expected=row['estimated_billable_characters']*plan['rate_cny_per_10000_weighted_characters']/10000
        assert math.isfinite(expected) and expected>0 and abs(cost-round(expected,6))<1e-8,'Estimate differs from price/character basis'
    cfg=read(ROOT/'默认配置/声音.json');cached=out/'cache';receipts=out/'receipts';cached.mkdir(parents=True,exist_ok=True);receipts.mkdir(exist_ok=True)
    pending=[];seen_keys=set();prior_cost=0
    for rp in receipts.rglob('*.json'):
        v=read(rp);prior_cost+=float(v.get('estimated_cost_cny',0))
    for row in rows:
        assert digest(row['request'])==row['cache_key'],'Request content/hash mismatch'
        k=row['cache_key']
        if k in seen_keys:continue
        seen_keys.add(k)
        rp=receipts/(k+'.json');mp=cached/(k+'.mp3')
        if rp.exists():
            r=read(rp)
            if r.get('status')=='completed' and mp.exists() and r.get('audio_sha256')==sha(mp):continue
            if retry_rejected and r.get('status')=='explicit_rejection_no_audio' and r.get('status_code')==1002:
                archive=receipts/'confirmed_rejections';archive.mkdir(exist_ok=True)
                dest=archive/(k+'_'+str(time.time_ns())+'.json');rp.replace(dest)
            else:raise RuntimeError('Existing incomplete/uncertain request: reconcile it before retry; '+row['id'])
        pending.append(row)
    required=prior_cost+sum(r['estimated_cost_cny'] for r in pending)
    if required>budget+1e-8:raise RuntimeError(f'Budget cap exceeded: conservative reservation {required:.6f} > {budget:.6f} CNY')
    if not pending:
        print(json.dumps({'status':'cache_hit','paid_calls':0,'selected':len(rows)}));return
    authorization=authorization_check(auth_path,plan_path,plan,pending,budget)
    if authorization.get('mock_only') and transport is None:raise ValueError('Mock authorization cannot call a real API')
    reserved_for_auth=sum(1 for p in receipts.rglob('*.json') if read(p).get('authorization_sha256')==sha(auth_path))
    if reserved_for_auth+len(pending)>authorization['max_new_requests']:raise ValueError('Maximum newly authorized TTS requests exceeded')
    key='offline-test-placeholder' if transport is not None else os.environ.get('MINIMAX_API_KEY','').strip()
    if not key:raise RuntimeError('MINIMAX_API_KEY is required only for execute; no credential file is read')
    session=transport if transport is not None else requests.Session();session.trust_env=False;submitted=0
    for row in pending:
        if submitted:time.sleep(cfg['tts_execution']['request_interval_seconds'])
        k=row['cache_key'];rp=receipts/(k+'.json');mp=cached/(k+'.mp3')
        receipt={'id':row['id'],'cache_key':k,'plan_sha256':sha(plan_path),'authorization_sha256':sha(auth_path),'price_evidence_sha256':authorization['price_basis']['evidence_sha256'],'started_at':now(),'status':'submitted_awaiting_response','estimated_cost_cny':row['estimated_cost_cny'],'request_without_secret':row['request']}
        save(rp,receipt);submitted+=1
        try:
            response=session.post(cfg['tts_execution']['endpoint'],headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=row['request'],timeout=(20,180))
            receipt['http_status']=response.status_code
            if response.status_code!=200:raise RuntimeError('http_non_200')
            body=response.json();code=body.get('base_resp',{}).get('status_code');receipt['status_code']=code;receipt['trace_id']=body.get('trace_id')
            data=body.get('data') or {};audio=data.get('audio')
            if code!=0:
                receipt['status']='explicit_rejection_no_audio' if not audio else 'uncertain_error_with_audio'
                save(rp,receipt);raise RuntimeError('Provider error; no automatic retry')
            if not audio:raise RuntimeError('success_without_audio')
            temp=mp.with_suffix('.tmp');temp.write_bytes(bytes.fromhex(audio));temp.replace(mp)
            receipt.update(status='completed',audio_sha256=sha(mp),audio_file='cache/'+mp.name,usage_characters=body.get('extra_info',{}).get('usage_characters'),completed_at=now())
            # Fetch can be retried separately without repeating speech synthesis.
            url=data.get('subtitle_file') or body.get('subtitle_file')
            if url:
                try:
                    sub=session.get(url,timeout=30);sub.raise_for_status();sp=cached/(k+'_words.json');save(sp,sub.json());receipt['provider_subtitle_file']='cache/'+sp.name
                except Exception as exc:receipt['subtitle_fetch_error_type']=type(exc).__name__;receipt['subtitle_fetch_requires_recovery']=True
            for name in ['subtitle','subtitles']:
                if data.get(name):
                    sp=cached/(k+'_words.json');save(sp,data[name]);receipt['provider_subtitle_file']='cache/'+sp.name
            save(rp,receipt)
        except Exception as exc:
            if receipt['status']=='submitted_awaiting_response':receipt['status']='submission_uncertain_requires_reconciliation'
            receipt['exception_type']=type(exc).__name__;save(rp,receipt)
            write_ledger(out,plan_path,budget);raise RuntimeError('TTS stopped; inspect receipt '+rp.name+'; no automatic retry') from None
        write_ledger(out,plan_path,budget)
        print(json.dumps({'id':row['id'],'status':receipt['status'],'paid_attempts_this_run':submitted},ensure_ascii=False),flush=True)
    write_ledger(out,plan_path,budget)
def write_ledger(out,plan_path,budget):
    rows=[read(p) for p in (out/'receipts').rglob('*.json')]
    save(out/'ledger.json',{'plan_sha256':sha(plan_path),'budget_cap_cny':budget,'attempts':len(rows),
        'completed':sum(r['status']=='completed' for r in rows),'estimated_reserved_cny':round(sum(r['estimated_cost_cny'] for r in rows),6),
        'billing_verified':False,'records':rows,'updated_at':now()})
def main():
    ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='action',required=True)
    p=sp.add_parser('plan');p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--rate-cny-per-10k',type=float,default=3.5)
    p=sp.add_parser('execute');p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--budget-cny',type=float,required=True);p.add_argument('--only',nargs='*');p.add_argument('--retry-confirmed-rejections',action='store_true');p.add_argument('--authorization',type=Path,help='Required for new paid requests; not needed for verified cached speech')
    a=ap.parse_args()
    if a.action=='plan':make_plan(a.input,a.output,a.rate_cny_per_10k)
    else:execute(a.plan,a.output,a.budget_cny,a.only,a.retry_confirmed_rejections,a.authorization)
if __name__=='__main__':main()
