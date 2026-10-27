"""只读原始 JPL 数据、重算坐标、核验历史七节点；不联网、不写回证据。"""
from pathlib import Path
import csv, hashlib, json, math
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'参考库/动画/01_星月与日期'
RAW=BASE/'数据/原始JPL'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(raw):
    block=raw.split('$$SOE',1)[1].split('$$EOE',1)[0]
    return [next(csv.reader([line])) for line in block.splitlines() if line.strip()]

def main():
    sky=read(BASE/'数据/sky_positions.json');saved=read(BASE/'数据/金星计算演示.json')
    original=read(RAW/'astro_horizons_jpl.json')
    original['bodies']['Venus']=read(RAW/'astro_venus_horizons_jpl.json')
    node_checks=[]
    for obj in sky['objects']:
        body=obj['id'];source=original['bodies'][body]['response']['result'];data=rows(source)
        assert len(data)==len(obj['nodes'])==7
        for i,(r,n) in enumerate(zip(data,obj['nodes'])):
            assert abs(float(r[3])-n['az_deg'])<1e-9 and abs(float(r[4])-n['alt_deg'])<1e-9
            assert math.isfinite(n['az_deg']) and 0<=n['az_deg']<360 and -90<=n['alt_deg']<=90
        node_checks.append({'body':body,'raw_nodes_matched':7})
    params=read(RAW/'JPL_Venus_参数.json')['params']
    assert params['SITE_COORD']=="'120.3,30.2,0.01'" and params['APPARENT']=="'AIRLESS'"
    record=next(r for r in rows(read(RAW/'JPL_Venus_原始返回.json')['result']) if r[0].strip()=='2010-Jul-07 12:40')
    ra,dec,jaz,jalt,last=map(float,record[3:8]);given=saved['jpl_direct_inputs']
    assert [ra,dec,last]==[given['alpha_ra_deg'],given['delta_dec_deg'],given['LAST_decimal_hours']]
    phi=math.radians(saved['query_inputs']['geodetic_latitude_north_deg']);delta=math.radians(dec)
    hour=math.radians(15*last-ra)
    east=-math.cos(delta)*math.sin(hour)
    north=math.cos(phi)*math.sin(delta)-math.sin(phi)*math.cos(delta)*math.cos(hour)
    up=math.sin(phi)*math.sin(delta)+math.cos(phi)*math.cos(delta)*math.cos(hour)
    alt=math.degrees(math.asin(up));az=math.degrees(math.atan2(east,north))%360
    assert abs(alt-jalt)<1e-8 and abs(az-jaz)<1e-8
    assert abs(east*east+north*north+up*up-1)<1e-12
    failed=read(BASE/'数据/历史失败请求/天空每分钟位置.json')
    assert failed['status']!='complete' and len(failed['objects'])==0
    report={'status':'passed','date_local':'2026-10-26','seven_bodies_twenty_minute_nodes':node_checks,
        'venus_coordinate_conversion':{'az_deg':az,'alt_deg':alt,'difference_from_printed_jpl_az':az-jaz,'difference_from_printed_jpl_alt':alt-jalt,'unit_vector_squared':east*east+north*north+up*up},
        'one_minute_nodes':'historical_fetch_failed_not_used','network_calls':0,'paid_api_calls':0,
        'source_files_modified':False,'limitation':'同一星历打印输入的计算一致性；不是现场观测精度，不是独立重新求解天体轨道。'}
    out=BASE/'独立重渲染';out.mkdir(exist_ok=True);(out/'数据核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
