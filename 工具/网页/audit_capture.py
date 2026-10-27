#!/usr/bin/env python3
"""Check original resource/screenshot hashes and DOM-to-pixel mappings. Visual review stays explicit."""
from pathlib import Path
import argparse, hashlib, json, math
from PIL import Image

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('capture',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--visual-note',default='');a=ap.parse_args()
 cp=a.capture.resolve();base=cp.parent;c=json.loads(cp.read_text('utf-8-sig'));checks=[]
 def check(name,passed,detail=None):checks.append({'check':name,'passed':bool(passed),'detail':detail})
 check('capture_not_failed',c['status']=='captured_coordinate_audit_required')
 check('original_text_not_retyped',c['source_text_rewritten'] is False)
 check('no_css_injected',c['css_override_injected'] is False)
 if c['mode']=='archived_html':check('no_network_in_archived_mode',c['network_requests_sent']==0)
 for f in c['files']:
  p=base/f['path'];check('file_hash:'+f['path'],p.exists() and sha(p)==f['sha256'])
 for r in c['regions']:
  p=base/r['image'];im=Image.open(p);x,y,w,h=[r['clip_css'][k] for k in ['x','y','width','height']];dpr=c['device_scale_factor']
  check(r['id']+':screenshot_dimensions',abs(im.width-w*dpr)<=1.01 and abs(im.height-h*dpr)<=1.01,list(im.size))
  check(r['id']+':quoted_context_retained',r['quote'] in r['context_text'])
  check(r['id']+':quote_hash',hashlib.sha256(r['quote'].encode()).hexdigest()==r['quote_text_sha256'])
  def boxes(label,css,pixels):
   check(label+':same_box_count',len(css)==len(pixels))
   for i,(cr,pr) in enumerate(zip(css,pixels)):
    expected=[(cr[0]-x)*dpr,(cr[1]-y)*dpr,(cr[2]-x)*dpr,(cr[3]-y)*dpr]
    check(label+f':transform_{i}',max(abs(u-v) for u,v in zip(expected,pr))<.001)
    check(label+f':in_capture_{i}',-.01<=pr[0]<pr[2]<=im.width+1.01 and -.01<=pr[1]<pr[3]<=im.height+1.01)
  boxes(r['id']+':full_quote',r['quote_rects_css_document'],r['quote_rects_image_pixels'])
  for m in r['marks']:
   check(r['id']+':mark_is_original:'+m['id'],m['quote'] in r['quote'])
   boxes(r['id']+':mark:'+m['id'],m['rects_css_document'],m['rects_image_pixels'])
 passed=all(x['passed'] for x in checks);d={'status':'passed_with_visual_note' if passed and a.visual_note else 'technical_passed_visual_pending' if passed else 'failed','capture':str(cp),'capture_sha256':sha(cp),'checks':checks,'visual_review':{'performed':bool(a.visual_note),'note':a.visual_note or 'Review actual captured and encoded images before production.'},'scope':'Integrity and coordinate geometry. Does not independently prove the source claims or copyright ownership.'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps({'status':d['status'],'checks':len(checks),'failures':[x for x in checks if not x['passed']]},ensure_ascii=False))
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()
