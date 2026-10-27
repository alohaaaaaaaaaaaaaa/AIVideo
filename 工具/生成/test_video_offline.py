#!/usr/bin/env python3
"""No network and no key: fake provider validates state machine, cost caps and CDN headers."""
from pathlib import Path
import tempfile,json
import av,numpy as np
import video
class Response:
 def __init__(self,data=None,content=b''):self.status_code=200;self.data=data;self.content=content
 def json(self):return self.data
 def iter_content(self,n):yield self.content
class Fake:
 def __init__(self,uncertain=False,content=b''):self.posts=0;self.gets=[];self.uncertain=uncertain;self.content=content
 def post(self,url,**kw):
  self.posts+=1
  if self.uncertain:raise TimeoutError('simulated accepted-but-response-lost')
  return Response({'task_id':'mock-task-001','base_resp':{'status_code':0}})
 def get(self,url,**kw):
  self.gets.append({'url':url,'headers':kw.get('headers',{})})
  if '/query/' in url:return Response({'task_id':'mock-task-001','status':'Success','file_id':'1234','base_resp':{'status_code':0}})
  if '/files/' in url:return Response({'file':{'file_id':1234,'bytes':len(self.content),'download_url':'https://cdn.example.invalid/mock.mp4'},'base_resp':{'status_code':0}})
  assert 'Authorization' not in kw.get('headers',{}),'Credential leaked to CDN';return Response(content=self.content)
def main():
 here=Path(__file__).parent;report={};video.key_header=lambda:{'Authorization':'Bearer mock-not-real','Content-Type':'application/json'}
 with tempfile.TemporaryDirectory(prefix='aziya-video-mock-') as tmp:
  out=Path(tmp);source=out/'shots.json';plan=out/'plan.json';price=out/'mock-price.txt';price.write_text('MOCK ONLY, not a current provider quotation')
  video.save(source,{'shots':[{'id':'N001','prompt':'MOCK TEST ONLY. A plain empty frame; do not actually generate.','purpose':'offline state machine test'}]});data=video.plan(source,plan,3.5)
  auth=out/'auth.json';video.save(auth,{'approved':True,'mock_only':True,'plan_sha256':video.sha(plan),'approval_reference':'mock-only simulated approval','scope':'offline fake transport','approved_shot_ids':['N001'],'budget_cap_cny':3.5,'max_new_tasks':1,'price_basis':{'verified_for_this_plan':True,'checked_at':'mock','source_url':'https://example.invalid/mock','evidence_file':price.name,'evidence_sha256':video.sha(price),'unit_prices_cny':{'N001':3.5}}})
  fake=Fake();receipts=out/'run';video.submit(plan,receipts,auth,3.5,transport=fake);video.submit(plan,receipts,auth,3.5,transport=fake);assert fake.posts==1;report['duplicate_submit_new_paid_calls']=0
  rp=next((receipts/'receipts').glob('*.json'));video.query(rp,transport=fake);assert fake.posts==1;report['query_does_not_submit']=True
  asset=here.parent/'媒体/离线测试/导出/clean.mp4';blob=asset.read_bytes();fake.content=blob
  try:video.download(rp,out/'wrong_resolution.mp4',transport=fake,cdn_transport=Fake(content=blob))
  except ValueError as exc:
   assert 'resolution' in str(exc);report['wrong_resolution_rejected']=True
  else:raise AssertionError('Low-resolution result accepted for 1080P request')
  asset=out/'1080p6s.mp4'
  with av.open(str(asset),'w') as c:
   v=c.add_stream('libx264',rate=24);v.width=1920;v.height=1080;v.pix_fmt='yuv420p';v.options={'preset':'ultrafast','crf':'40'}
   pixels=np.zeros((1080,1920,3),dtype=np.uint8)
   for i in range(144):
    frame=av.VideoFrame.from_ndarray(pixels,format='rgb24')
    for packet in v.encode(frame):c.mux(packet)
   for packet in v.encode():c.mux(packet)
  blob=asset.read_bytes();fake.content=blob;cdn=Fake(content=blob);video.download(rp,out/'download.mp4',transport=fake,cdn_transport=cdn);assert cdn.gets[0]['headers']=={};report['cdn_receives_no_authorization']=True;report['mock_download_full_decode']=True
  uncertain=Fake(uncertain=True);uncertain_out=out/'uncertain'
  try:video.submit(plan,uncertain_out,auth,3.5,transport=uncertain)
  except RuntimeError:pass
  else:raise AssertionError('timeout not stopped')
  try:video.submit(plan,uncertain_out,auth,3.5,transport=uncertain)
  except RuntimeError:pass
  else:raise AssertionError('uncertain submission retried')
  assert uncertain.posts==1;report['uncertain_submission_blocks_resubmit']=True
  try:video.submit(plan,out/'budget',auth,3.49,transport=Fake())
  except ValueError:report['budget_cap_enforced']=True
  else:raise AssertionError('overspend')
  a=video.read(auth);a['price_basis']['verified_for_this_plan']=False;video.save(auth,a)
  try:video.submit(plan,out/'price',auth,3.5,transport=Fake())
  except ValueError:report['unverified_current_price_blocks_submit']=True
  else:raise AssertionError('unverified price accepted')
 report.update(status='passed',real_network_calls=0,real_paid_calls=0,credentials_read=False)
 video.save(here/'离线状态机测试.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
