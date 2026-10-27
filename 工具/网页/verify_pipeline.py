#!/usr/bin/env python3
"""Offline fixtures and loopback HTTP verify evidence integrity failures; these are NOT source evidence."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,json,subprocess,sys,threading,shutil

HERE=Path(__file__).resolve().parent
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 quote='原文跨节点必须连贯保留';html='<meta charset="utf-8"><h1>技术测试夹具，不是新闻证据</h1><p><span>原文跨</span><b>节点</b>必须连贯保留</p>';(out/'fixture.html').write_text(html,'utf-8');results=[]
 basic={'mode':'archived_html','url':'http://offline.test/fixture','html':'fixture.html','viewport':[800,600],'device_scale_factor':2,'regions':[{'id':'test','quote':quote,'marks':[{'id':'across','quote':'跨节点'}]}]}
 def run_case(name,cfg,expected_success,error_part=None):
  p=out/(name+'.json');dump(p,cfg);target=out/name;r=subprocess.run([sys.executable,str(HERE/'capture_evidence.py'),str(p),'--output',str(target)],capture_output=True,text=True);c=json.loads((target/'capture.json').read_text());ok=(r.returncode==0)==expected_success
  if error_part:ok=ok and error_part in c.get('error','')
  if not expected_success:ok=ok and c['status']=='failed_do_not_use_as_complete_evidence'
  results.append({'case':name,'passed':ok,'expected_success':expected_success,'returncode':r.returncode,'status':c['status'],'error':c.get('error'),'requests':c.get('network_requests_sent'),'report':str(target/'capture.json')});return target,c
 good,c=run_case('01_cross_node_exact_match',basic,True);assert c['network_requests_sent']==0
 # The returned original quote and mark must match across inline DOM elements.
 results.append({'case':'cross_node_quote_and_mark_exact','passed':c['regions'][0]['quote']==quote and c['regions'][0]['marks'][0]['quote']=='跨节点'})
 (out/'duplicate.html').write_text(html+html,'utf-8');run_case('02_ambiguous_quote_rejected',dict(basic,html='duplicate.html'),False,'找到 2 处')
 run_case('03_missing_quote_rejected',dict(basic,regions=[{'id':'test','quote':'不存在的引文'}]),False,'找到 0 处')
 run_case('04_crop_truncation_rejected',dict(basic,regions=[{'id':'test','quote':quote,'view':{'x':0,'width':10,'height':10}}]),False,'选区不能裁断引用全文')
 class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
   body=html.encode();self.send_response(403 if self.path=='/forbidden' else 200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();host='http://127.0.0.1:'+str(server.server_port)
 try:
  public={k:v for k,v in basic.items() if k!='html'};public.update(mode='public_url',url=host+'/fixture');_,c=run_case('05_public_mode_loopback_get',public,True)
  results.append({'case':'public_html_archived','passed':any(r['role']=='document' for r in c['resources']) and all(r.get('method') in ['GET','HEAD'] for r in c['requests'])})
  run_case('06_http403_stops',dict(public,url=host+'/forbidden'),False,'停止')
 finally:server.shutdown();server.server_close()
 tamper=out/'07_tamper_fixture';shutil.copytree(good,tamper);p=tamper/'原始资源/main_original.html';p.write_bytes(p.read_bytes()+b'changed for integrity test')
 report=out/'07_tamper_audit.json';r=subprocess.run([sys.executable,str(HERE/'audit_capture.py'),str(tamper/'capture.json'),'--output',str(report)],capture_output=True,text=True);j=json.loads(report.read_text());results.append({'case':'original_bytes_change_rejected','passed':r.returncode!=0 and j['status']=='failed','report':str(report)})
 summary={'status':'passed' if all(r['passed'] for r in results) else 'failed','scope':'Generated fixtures + local loopback only; no real-site browsing claims','cases':results,'paid_api_calls':0,'external_network_required':False};dump(out/'失败模式核验.json',summary);print(json.dumps(summary,ensure_ascii=False))
 if summary['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
