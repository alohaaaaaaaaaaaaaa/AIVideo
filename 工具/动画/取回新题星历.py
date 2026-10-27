"""按新选题的明确参数取回免费 NASA/JPL Horizons 星历，保留原始响应。
先写查询配置，运行 --config ... --output ...。不会自动覆盖历史案例。
输出状态不完整时不能进入动画。新题渲染器必须据新数据另建/核验。
"""
from pathlib import Path
import argparse,csv,datetime,hashlib,json,subprocess,urllib.parse
ROOT=Path(__file__).resolve().parents[2]
def resolve(s):
 p=Path(s)
 if p.is_absolute():raise ValueError('只接受新项目相对路径')
 p=(ROOT/p).resolve()
 if not p.is_relative_to(ROOT):raise ValueError('路径越界')
 return p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
 cfg=json.loads(resolve(args.config).read_text());out=resolve(args.output)
 if out.exists():raise ValueError('输出目录已存在，请给此次查询建立新目录，保留旧证据')
 lon,lat,height=cfg['observer']['longitude_east_deg'],cfg['observer']['latitude_north_deg'],cfg['observer']['height_km']
 assert all(isinstance(v,(int,float)) for v in [lon,lat,height]), '请先填写新题的经纬度和海拔，不能使用空模板'
 assert -180<=lon<=180 and -90<=lat<=90 and height>=-.5
 assert cfg['observer']['role'] and cfg['display_timezone'] and cfg['event_time_uncertainty']
 start=datetime.datetime.fromisoformat(cfg['start_utc'].replace('Z','+00:00'));stop=datetime.datetime.fromisoformat(cfg['stop_utc'].replace('Z','+00:00'))
 assert start.utcoffset()==datetime.timedelta(0) and stop.utcoffset()==datetime.timedelta(0) and stop>start
 step=cfg['step_minutes'];assert isinstance(step,int) and step>0
 expected=int((stop-start).total_seconds()//(step*60))+1
 out.mkdir(parents=True);(out/'query_config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
 common={'format':'json','EPHEM_TYPE':"'OBSERVER'",'CENTER':"'coord@399'",'COORD_TYPE':"'GEODETIC'",'SITE_COORD':f"'{lon},{lat},{height}'",'START_TIME':f"'{start:%Y-%m-%d %H:%M}'",'STOP_TIME':f"'{stop:%Y-%m-%d %H:%M}'",'STEP_SIZE':f"'{step} m'",'QUANTITIES':"'2,4,7'",'CSV_FORMAT':"'YES'",'APPARENT':"'AIRLESS'",'ANG_FORMAT':"'DEG'",'EXTRA_PREC':"'YES'"}
 records=[];objects=[]
 for target in cfg['targets']:
  key=target['id'];assert key.isascii() and key.replace('_','').isalnum()
  params={**common,'COMMAND':"'"+str(target['horizons_command'])+"'"};url='https://ssd.jpl.nasa.gov/api/horizons.api?'+urllib.parse.urlencode(params)
  dest=out/(key+'_raw.json');rec={'id':key,'url':url,'params':params,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paid_api_call':False}
  try:
   subprocess.run(['curl','--fail','--silent','--show-error','--location','--connect-timeout','12','--max-time','45','--output',str(dest),url],check=True)
   payload=json.loads(dest.read_text());assert 'error' not in payload,payload.get('error');raw=payload['result'];assert 'AIRLESS' in raw
   block=raw.split('$$SOE',1)[1].split('$$EOE',1)[0];nodes=[]
   for line in block.splitlines():
    if not line.strip():continue
    row=next(csv.reader([line]));when=datetime.datetime.strptime(row[0].strip(),'%Y-%b-%d %H:%M').replace(tzinfo=datetime.timezone.utc)
    assert when==start+datetime.timedelta(minutes=step*len(nodes))
    ra,dec,az,alt,last=map(float,row[3:8]);nodes.append({'utc':when.isoformat(),'ra_deg':ra,'dec_deg':dec,'az_deg':az,'alt_deg':alt,'last_hours':last,'raw_row':line})
   assert len(nodes)==expected
   rec.update(status='success',sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),nodes=len(nodes),raw_path=dest.name)
   objects.append({'id':key,'name':target['name'],'nodes':nodes,'raw_path':dest.name})
  except Exception as exc:rec.update(status='failed',error=str(exc))
  records.append(rec);(out/(key+'_request.json')).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(key,rec['status'],flush=True)
 status='complete' if len(objects)==len(cfg['targets']) else 'incomplete_do_not_render'
 result={'status':status,'query':cfg,'objects':objects,'requests':records,'method':'AIRLESS 站心视位置；节点间绘图插值另行标识；标记大小不是亮度或视直径。'}
 (out/'dataset.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 if status!='complete':raise SystemExit('数据不完整，保留失败记录，禁止拿缺失结果当作天体不存在。')
if __name__=='__main__':main()
