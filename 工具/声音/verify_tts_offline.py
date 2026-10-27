"""Offline fake-transport tests; never read credentials or submit paid requests."""
from pathlib import Path
import contextlib,io,json,tempfile
import requests
import tts
ROOT=Path(__file__).resolve().parents[2]
class Fake:
 trust_env=False
 def __init__(self,fail=False):self.posts=0;self.fail=fail
 def post(self,*args,**kwargs):
  self.posts+=1
  if self.fail:raise requests.Timeout('offline simulated timeout')
  class Response:
   status_code=200
   def json(self):return {'base_resp':{'status_code':0},'data':{'audio':b'offline-audio-bytes-not-for-playback'.hex()},'extra_info':{'usage_characters':10},'trace_id':'offline'}
  return Response()
def refused(fn):
 try:fn()
 except (ValueError,RuntimeError,AssertionError):return True
 raise AssertionError('Invalid request unexpectedly accepted')
def main():
 with tempfile.TemporaryDirectory() as d:
  d=Path(d);source=ROOT/'参考库/声音/TTS输入示例.json';plan=d/'plan.json'
  with contextlib.redirect_stdout(io.StringIO()):tts.make_plan(source,plan,3.5)
  data=tts.read(plan);ids=[r['id'] for r in data['paragraphs']];ev=d/'price.txt';ev.write_text('OFFLINE MOCK. No real quotation or permission.')
  auth={'approved':True,'mock_only':True,'plan_sha256':tts.sha(plan),'approval_reference':'OFFLINE MOCK ONLY, cannot authorize network','scope':'unit-test fake transport','approved_paragraph_ids':ids,'budget_cap_cny':1,'max_new_requests':len(ids),'price_basis':{'verified_for_this_plan':True,'checked_at':tts.now(),'source_url':'https://example.invalid/price','model':'speech-2.8-hd','rate_cny_per_10000_weighted_characters':3.5,'evidence_file':ev.name,'evidence_sha256':tts.sha(ev)}}
  ap=d/'auth.json';tts.save(ap,auth)
  fake=Fake()
  assert refused(lambda:tts.execute(plan,d/'missing',1,None,False,transport=fake)) and fake.posts==0
  assert refused(lambda:tts.execute(plan,d/'realrefused',1,None,False,ap)) and fake.posts==0
  for field,value in [('plan_sha256','bad'),('approved_paragraph_ids',[]),('max_new_requests',0),('budget_cap_cny',.00001)]:
   bad=dict(auth);bad[field]=value;tts.save(ap,bad);assert refused(lambda:tts.execute(plan,d/('bad_'+field),1,None,False,ap,fake)) and fake.posts==0
  bad=dict(auth);bad['price_basis']={**auth['price_basis'],'evidence_sha256':'bad'};tts.save(ap,bad);assert refused(lambda:tts.execute(plan,d/'bad_price',1,None,False,ap,fake)) and fake.posts==0
  tts.save(ap,auth)
  with contextlib.redirect_stdout(io.StringIO()):tts.execute(plan,d/'ok',1,None,False,ap,fake)
  first=fake.posts
  with contextlib.redirect_stdout(io.StringIO()):tts.execute(plan,d/'ok',1,None,False,transport=fake)
  assert fake.posts==first==len({r['cache_key'] for r in data['paragraphs']})
  uncertain=Fake(True)
  assert refused(lambda:tts.execute(plan,d/'uncertain',1,None,False,ap,uncertain))
  assert refused(lambda:tts.execute(plan,d/'uncertain',1,None,False,ap,uncertain)) and uncertain.posts==1
  assert tts.billable_characters('啊子牙𠮷police。')==15
 result={'status':'passed','actual_paid_requests':0,'fake_transport_only':True,'missing_or_changed_approval_rejected_before_network':True,'price_evidence_bound_to_plan_model_and_hash':True,'budget_request_count_and_scope_enforced':True,'mock_authorization_refuses_real_network':True,'successful_cache_reused_without_reapproval_or_request':True,'uncertain_submission_not_automatically_repeated':True,'extended_Han_weighting_verified':True}
 tts.save(ROOT/'参考库/声音/TTS离线执行核验.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
