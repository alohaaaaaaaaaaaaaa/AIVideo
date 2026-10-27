"""逐次免费查询JPL，保存原始返回及121个一分钟节点；不改原资料目录。"""
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.parse
import urllib.request

HERE=Path(__file__).resolve().parent
OUT=HERE/'JPL_一分钟'
OUT.mkdir(parents=True,exist_ok=True)
BASE=HERE.parents[1]
OLD=json.loads((BASE/'数据/sky_positions.json').read_text(encoding='utf-8'))
OLD_OBJS={o['id']:o for o in OLD['objects']}
TARGETS=[('Sun','太阳','10'),('Moon','月亮','301'),('Mercury','水星','199'),('Venus','金星','299'),('Mars','火星','499'),('Jupiter','木星','599'),('Saturn','土星','699')]
COMMON={'format':'json','EPHEM_TYPE':"'OBSERVER'",'CENTER':"'coord@399'",'COORD_TYPE':"'GEODETIC'",'SITE_COORD':"'120.3,30.2,0.01'",'START_TIME':"'2010-07-07 12:00'",'STOP_TIME':"'2010-07-07 14:00'",'STEP_SIZE':"'1 m'",'QUANTITIES':"'4'",'CSV_FORMAT':"'YES'",'APPARENT':"'AIRLESS'",'ANG_FORMAT':"'DEG'",'EXTRA_PREC':"'YES'"}
log=[]
objects=[]
for body,name,code in TARGETS:
    params=dict(COMMON,COMMAND=f"'{code}'")
    url='https://ssd.jpl.nasa.gov/api/horizons.api?'+urllib.parse.urlencode(params)
    raw_path=OUT/f'{body}_原始返回.json'
    entry={'body_id':body,'url':url,'params':params,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'paid_api_call':False}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'XiaoshanResearch/1.0 (local video coordinate verification)'})
        with urllib.request.urlopen(req,timeout=35) as r:
            data=r.read()
            entry['status_code']=r.status
            entry['resolved_url']=r.url
        raw_path.write_bytes(data)
        response=json.loads(data)
        if 'error' in response:
            raise RuntimeError(response['error'])
        result=response['result']
        assert 'Center geodetic : 120.3, 30.2, .010' in result
        assert 'Atmos refraction: NO (AIRLESS)' in result
        (OUT/f'{body}_返回正文.txt').write_text(result,encoding='utf-8')
        block=result.split('$$SOE',1)[1].split('$$EOE',1)[0]
        nodes=[]
        for line in block.splitlines():
            if not line.strip(): continue
            cells=next(csv.reader([line]))
            t=datetime.strptime(cells[0].strip(),'%Y-%b-%d %H:%M').replace(tzinfo=timezone.utc)
            assert t==datetime(2010,7,7,12,tzinfo=timezone.utc)+timedelta(minutes=len(nodes))
            bjt=t.astimezone(timezone(timedelta(hours=8)))
            az,alt=float(cells[3]),float(cells[4])
            nodes.append({'index':len(nodes),'time_utc':t.isoformat().replace('+00:00','Z'),'time_beijing':bjt.isoformat(),'label':bjt.strftime('%H:%M'),'az_deg':az,'alt_deg':alt,'above_geometric_horizon':alt>0,'raw_row':line})
        assert len(nodes)==121
        max_diff=max(max(abs(old[k]-nodes[i*20][k]) for k in ('az_deg','alt_deg')) for i,old in enumerate(OLD_OBJS[body]['nodes']))
        assert max_diff<0.000001
        entry.update({'status':'success','source_file':str(raw_path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'nodes':121,'max_difference_from_saved_20min_nodes_deg':max_diff})
        objects.append({'id':body,'name':name,'role':OLD_OBJS[body]['role'],'primary':OLD_OBJS[body]['primary'],'nodes':nodes,'source_url':url,'raw_source':str(raw_path),'raw_sha256':entry['sha256']})
    except Exception as e:
        entry.update({'status':'failed','error':str(e)})
    log.append(entry)
    (OUT/f'{body}_参数与取回记录.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'fetch_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'body':body,'status':entry['status'],'nodes':entry.get('nodes'),'error':entry.get('error')},ensure_ascii=False),flush=True)

full={'schema_version':'1.0','status':'complete' if len(objects)==7 else 'partial_do_not_use_as_full_seven_object_animation','provider':'NASA/JPL Horizons','query_type':'free_official_ephemeris_query','paid_api_calls':0,'observer':OLD['observer'],'conventions':OLD['conventions'],'interval_minutes':1,'nodes_per_object':121,'date_beijing':'2010-07-07','start_beijing':'20:00','end_beijing':'22:00','objects':objects,'source_records':log,'limitations':OLD['limitations']+['本文件已取回每分钟真实星历节点；两分钟节点之间若为画面流畅而插值，应标动画插值，不称逐帧实测。','这些是JPL对历史时刻的星历计算结果，不是当晚摄像观测。']}
(HERE/'天空每分钟位置.json').write_text(json.dumps(full,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':full['status'],'objects':len(objects)},ensure_ascii=False),flush=True)
