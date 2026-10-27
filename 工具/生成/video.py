#!/usr/bin/env python3
"""MiniMax v1 T2V adapter. plan is offline. No blind retries; no credentials in files."""
from pathlib import Path
from contextlib import contextmanager
import argparse,datetime,hashlib,json,os,re
from urllib.parse import urlparse
import requests

DEFAULTS={'provider':'minimax-v1','base_url':'https://api.minimax.cn','model':'MiniMax-Hailuo-02','duration':6,'resolution':'1080P','prompt_optimizer':False,'aigc_watermark':False}
ALLOWED_HOSTS={'https://api.minimax.cn','https://api.minimax.io'}

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8');tmp.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def response_record(receipt,phase,body,http_status):
 # Retain the useful provider response without headers, signed URLs, prompts or credentials.
 safe={k:body[k] for k in ('task_id','status','file_id','video_width','video_height') if k in body}
 base=body.get('base_resp',{});msg=str(base.get('status_msg',''))
 key=os.environ.get('MINIMAX_API_KEY','')
 if key:msg=msg.replace(key,'[REDACTED]')
 msg=re.sub(r'https?://\S+','[URL REDACTED]',msg)
 safe['base_resp']={'status_code':base.get('status_code'),'status_msg':msg[:1000]}
 if isinstance(body.get('file'),dict):safe['file']={k:body['file'][k] for k in ('file_id','bytes','filename','purpose') if k in body['file']}
 receipt.setdefault('api_events',[]).append({'phase':phase,'at':now(),'http_status':http_status,'sanitized_response':safe})
def need(ok,message):
 if not ok:raise ValueError(message)
def session():
 s=requests.Session();s.trust_env=False;return s
def key_header():
 key=os.environ.get('MINIMAX_API_KEY','').strip();need(key,'MINIMAX_API_KEY required; credential files are never read');return {'Authorization':'Bearer '+key,'Content-Type':'application/json'}
def endpoint(config,path):
 need(config.get('provider')=='minimax-v1','Only minimax-v1 implemented; other providers need a reviewed adapter')
 base=config['base_url'].rstrip('/');need(base in ALLOWED_HOSTS,'Unreviewed API host; refusing to send credential');return base+path
@contextmanager
def lock(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with (out/'.submission.lock').open('a') as f:
  if os.name=='nt':
   import msvcrt
   f.seek(0);f.write('0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
  else:
   import fcntl
   fcntl.flock(f.fileno(),fcntl.LOCK_EX)
  try:yield
  finally:
   if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
def ledger(out,plan_path=None,budget=None):
 rows=[read(p) for p in (Path(out)/'receipts').glob('*.json')]
 previous=read(Path(out)/'ledger.json') if (Path(out)/'ledger.json').exists() else {}
 save(Path(out)/'ledger.json',{'plan_sha256':sha(plan_path) if plan_path else previous.get('plan_sha256'),'budget_cap_cny':budget if budget is not None else previous.get('budget_cap_cny'),'attempts':len(rows),'estimated_reserved_cny':round(sum(float(r['estimated_cost_cny']) for r in rows),6),'billing_verified':False,'records':rows,'updated_at':now()})

def plan(source,out,rate,config_path=None):
 data=read(source);cfg={**DEFAULTS,**(read(config_path) if config_path else {}),**data.get('config',{})}
 endpoint(cfg,'/v1/video_generation');need(rate>0,'rate must be positive')
 rows=[];ids=set()
 for row in data['shots']:
  sid=row['id'];need(re.fullmatch('[A-Za-z0-9_-]+',sid) and sid not in ids,'Unique safe shot ID required');ids.add(sid)
  request={k:cfg[k] for k in ['model','duration','resolution','prompt_optimizer','aigc_watermark']}
  overrides=row.get('request_override',{});need(set(overrides)<=set(request),'Unsupported request override; adapt API explicitly')
  request.update(overrides);request['prompt']=row['prompt'];need(isinstance(request['prompt'],str) and 0<len(request['prompt'])<=2000,'prompt must contain 1–2000 characters')
  if request['model'] in {'MiniMax-Hailuo-02','MiniMax-Hailuo-2.3'}:
   need((request['resolution'],request['duration']) in {('1080P',6),('768P',6),('768P',10)},'Unsupported Hailuo duration/resolution')
  elif request['model'] in {'T2V-01','T2V-01-Director'}:
   need((request['resolution'],request['duration'])==('720P',6),'Legacy T2V validated only for720P6s')
  else:raise ValueError('Model not in validated v1 set; verify official docs and add adapter')
  cost=float(row.get('estimated_cost_cny',rate));need(cost>0,'Shot price must be positive')
  rows.append({'id':sid,'purpose':row.get('purpose',''),'acceptance':row.get('acceptance',[]),'context_label':row.get('context_label','情境示意'),'request':request,'cache_key':digest({'provider':cfg['provider'],'base_url':cfg['base_url'],'request':request}),'estimated_cost_cny':cost})
 output={'schema_version':1,'created_at':now(),'source_filename':Path(source).name,'source_sha256':sha(source),'config':{'provider':cfg['provider'],'base_url':cfg['base_url']},'shots':rows,'estimated_total_cny':round(sum(x['estimated_cost_cny'] for x in rows),6),'price_basis':data.get('price_basis',{'kind':'unverified_estimate','note':'Caller-supplied estimate only; submit requires separately recorded current official price evidence. Actual billing remains unverified.'}),'billing_verified':False,'paid_calls':0}
 save(out,output);print(json.dumps({'plan':str(out),'plan_sha256':sha(out),'shots':len(rows),'estimated_total_cny':output['estimated_total_cny'],'paid_calls':0},ensure_ascii=False));return output

def authorization_check(auth_path,plan_path,plan_data,rows,budget):
 a=read(auth_path);need(a.get('approved') is True,'Authorization must record actual existing user approval')
 need(a.get('plan_sha256')==sha(plan_path),'Authorization must bind exact current plan hash')
 need(a.get('approval_reference') and a.get('scope'),'Record actual session approval/reference and concrete scope')
 need({r['id'] for r in rows}<=set(a.get('approved_shot_ids',[])),'Shots outside authorized scope')
 need(0<budget<=float(a['budget_cap_cny']),'CLI budget exceeds authorized cap')
 need(type(a.get('max_new_tasks')) is int and a['max_new_tasks']>=0,'max_new_tasks required')
 basis=a.get('price_basis',{});need(basis.get('verified_for_this_plan') is True,'Current price/model availability not verified')
 need(basis.get('checked_at') and basis.get('source_url') and basis.get('evidence_file'),'Current price evidence required')
 evidence=(Path(auth_path).parent/basis['evidence_file']).resolve();need(evidence.is_file() and sha(evidence)==basis.get('evidence_sha256'),'Price evidence missing or hash mismatch')
 prices=basis.get('unit_prices_cny',{});need(all(r['id'] in prices and abs(float(prices[r['id']])-r['estimated_cost_cny'])<1e-8 for r in rows),'Plan estimates must match verified per-shot prices')
 return a

def submit(plan_path,out,auth_path,budget,only=None,transport=None):
 out=Path(out);p=read(plan_path);rows=[r for r in p['shots'] if not only or r['id'] in only];need(rows,'No shots selected')
 a=authorization_check(auth_path,plan_path,p,rows,budget)
 need(not a.get('mock_only') or transport is not None,'Mock authorization cannot call a real API')
 with lock(out):
  receipts=out/'receipts';receipts.mkdir(exist_ok=True);pending=[];seen=set()
  for row in rows:
   k=digest({'provider':p['config']['provider'],'base_url':p['config']['base_url'],'request':row['request']});need(k==row['cache_key'],'Request content hash mismatch')
   if k in seen:continue
   seen.add(k);rp=receipts/(k+'.json')
   if rp.exists():
    prior=read(rp)
    if prior.get('task_id'):
     print(json.dumps({'id':row['id'],'status':'existing_task_use_query_or_download','task_id':prior['task_id'],'new_paid_calls':0}));continue
    raise RuntimeError('Existing submission without confirmed task ID; reconcile it, never resubmit blindly: '+row['id'])
   pending.append(row)
  existing=[read(rp) for rp in receipts.glob('*.json')]
  reserved=sum(float(r['estimated_cost_cny']) for r in existing)+sum(r['estimated_cost_cny'] for r in pending)
  need(reserved<=budget+1e-8,'Budget cap exceeded including every prior attempt/uncertain reservation')
  this_auth=[r for r in existing if r.get('authorization_sha256')==sha(auth_path)]
  need(len(this_auth)+len(pending)<=a['max_new_tasks'],'Authorized task-count cap exceeded')
  if not pending:return
  headers=key_header();client=transport or session();url=endpoint(p['config'],'/v1/video_generation')
  for row in pending:
   rp=receipts/(row['cache_key']+'.json');receipt={'id':row['id'],'cache_key':row['cache_key'],'config':p['config'],'plan_sha256':sha(plan_path),'authorization_sha256':sha(auth_path),'started_at':now(),'status':'submitted_awaiting_response','estimated_cost_cny':row['estimated_cost_cny'],'request_without_secret':row['request'],'context_label':row['context_label']};save(rp,receipt)
   try:
    response=client.post(url,headers=headers,json=row['request'],timeout=(20,120),allow_redirects=False);receipt['http_status']=response.status_code
    need(response.status_code==200,'Non-200 submission response')
    body=response.json();response_record(receipt,'submit',body,response.status_code);code=body.get('base_resp',{}).get('status_code');receipt['provider_status_code']=code
    task=str(body.get('task_id') or '')
    if task:receipt.update(task_id=task,status='submitted_with_task_id')
    elif code!=0:receipt['status']='explicit_rejection_no_task';save(rp,receipt);raise RuntimeError('Provider rejected submission; inspect before any revised generation')
    else:raise RuntimeError('Successful response without task ID is uncertain')
    save(rp,receipt)
   except Exception as exc:
    if receipt['status']=='submitted_awaiting_response':receipt['status']='submission_uncertain_requires_reconciliation'
    receipt['exception_type']=type(exc).__name__;save(rp,receipt);ledger(out,plan_path,budget);raise RuntimeError('Submission stopped; inspect receipt; no automatic retry') from None
   ledger(out,plan_path,budget);print(json.dumps({'id':row['id'],'task_id':receipt['task_id'],'status':receipt['status']},ensure_ascii=False),flush=True)

def query(receipt_path,transport=None):
 rp=Path(receipt_path);r=read(rp);need(r.get('task_id'),'Task ID absent: reconcile provider account/task log; never issue another submit to discover it')
 response=(transport or session()).get(endpoint(r['config'],'/v1/query/video_generation'),headers=key_header(),params={'task_id':r['task_id']},timeout=30,allow_redirects=False)
 need(response.status_code==200,'Query HTTP error; query is safe to run again later')
 body=response.json();response_record(r,'query',body,response.status_code);save(rp,r);need(body.get('base_resp',{}).get('status_code')==0,'Query provider error; no new generation issued')
 need(str(body.get('task_id',r['task_id']))==r['task_id'],'Task response mismatch')
 status=body.get('status');need(status in {'Preparing','Queueing','Processing','Success','Fail'},'Unknown provider status')
 r['last_query_at']=now();r['provider_task_status']=status
 if status=='Success':
  need(body.get('file_id'),'Success without file ID: query again, do not submit');r['file_id']=str(body['file_id']);r['status']='downloaded' if r.get('output_sha256') else 'ready_to_download';r['provider_size']=[body.get('video_width'),body.get('video_height')]
 elif status=='Fail':r['status']='provider_task_failed_requires_review'
 else:r['status']='processing'
 save(rp,r);ledger(rp.parent.parent);print(json.dumps({'task_id':r['task_id'],'status':status,'file_id':r.get('file_id'),'new_paid_calls':0}));return r

def download(receipt_path,output=None,transport=None,cdn_transport=None):
 rp=Path(receipt_path);r=read(rp);need(r.get('file_id'),'Query first; download needs confirmed file ID')
 target=Path(output) if output else rp.parent.parent/'downloaded'/(r['id']+'.mp4');target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and r.get('output_sha256')==sha(target):
  print(json.dumps({'status':'download_cache_hit','file':str(target),'new_paid_calls':0}));return
 need(not target.exists(),'Refusing to overwrite a different video; choose new --output path')
 response=(transport or session()).get(endpoint(r['config'],'/v1/files/retrieve'),headers=key_header(),params={'file_id':r['file_id']},timeout=30,allow_redirects=False)
 need(response.status_code==200,'File retrieve HTTP error');body=response.json();response_record(r,'retrieve',body,response.status_code);save(rp,r);need(body.get('base_resp',{}).get('status_code')==0,'File retrieve provider error')
 file=body['file'];need(str(file['file_id'])==r['file_id'],'File ID mismatch');url=file['download_url'];parsed=urlparse(url);need(parsed.scheme=='https' and parsed.hostname and not parsed.username,'Download requires HTTPS provider URL')
 # Fresh unauthenticated session; never forward API authorization or cookies to CDN.
 cdn=cdn_transport or session();response=cdn.get(url,timeout=(20,180),stream=True,allow_redirects=True)
 need(response.status_code==200,'Download HTTP error; retrieve a fresh URL and retry download only')
 partial=target.with_suffix('.part');size=0
 try:
  with partial.open('wb') as f:
   for block in response.iter_content(2**20):
    if block:size+=len(block);need(size<=2*1024**3,'Unexpected video >2GiB');f.write(block)
  need(size>0 and (not file.get('bytes') or size==int(file['bytes'])),'Downloaded file size mismatch')
  import av
  count=0;pts=[]
  with av.open(str(partial)) as c:
   need(bool(c.streams.video),'Downloaded result contains no video');v=c.streams.video[0]
   need(v.average_rate is not None and float(v.average_rate)>0,'Downloaded video has no valid frame rate')
   fps=float(v.average_rate)
   for frame in c.decode(v):
    count+=1;need(frame.pts is not None,'Decoded frame lacks presentation time');pts.append(float(frame.pts*frame.time_base))
   need(count>1 and all(b>a for a,b in zip(pts,pts[1:])),'Decoded video has nonmonotonic or insufficient frames')
   actual_duration=float(v.duration*v.time_base) if v.duration is not None else pts[-1]-pts[0]+1/fps
   timeline_duration=pts[-1]-pts[0]+1/fps
   need(abs(actual_duration-float(r['request_without_secret']['duration']))<.2 and abs(timeline_duration-actual_duration)<.1,'Downloaded duration differs from request or decoded timeline')
   requested_short_edge=int(r['request_without_secret']['resolution'].rstrip('P'))
   need(min(v.width,v.height)==requested_short_edge,'Downloaded resolution differs from request')
   need(all(abs((b-a)-1/fps)<max(.002,.1/fps) for a,b in zip(pts,pts[1:])),'Downloaded frame timing is irregular')
   info={'width':v.width,'height':v.height,'fps':fps,'duration':actual_duration,'timeline_duration':timeline_duration,'frames':count,'full_decode':True,'monotonic_pts':True,'uniform_frame_timing':True,'requested_resolution_verified':True}
  partial.replace(target)
 except Exception:
  if partial.exists():partial.unlink()
  raise
 r.update(status='downloaded',completed_at=now(),output_file=str(target.resolve()),output_sha256=sha(target),download_bytes=size,download_host=parsed.hostname,decode=info,native_label_verified=False,needs_context_label=True)
 save(rp,r);ledger(rp.parent.parent);print(json.dumps({'file':str(target),'sha256':r['output_sha256'],'new_paid_calls':0,'needs_context_label':True},ensure_ascii=False));return r

def main():
 ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='action',required=True)
 p=sp.add_parser('plan');p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--config',type=Path);p.add_argument('--rate-cny-per-video',type=float,default=3.5)
 p=sp.add_parser('submit');p.add_argument('--plan',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--authorization',required=True,type=Path);p.add_argument('--budget-cny',required=True,type=float);p.add_argument('--only',nargs='*')
 p=sp.add_parser('query');p.add_argument('--receipt',required=True,type=Path)
 p=sp.add_parser('download');p.add_argument('--receipt',required=True,type=Path);p.add_argument('--output',type=Path)
 a=ap.parse_args()
 if a.action=='plan':plan(a.input,a.output,a.rate_cny_per_video,a.config)
 elif a.action=='submit':submit(a.plan,a.output,a.authorization,a.budget_cny,a.only)
 elif a.action=='query':query(a.receipt)
 else:download(a.receipt,a.output)
if __name__=='__main__':main()
