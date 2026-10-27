"""只读原始数据，重新核对金星演示中的标量和向量；不计算轨道。"""
import csv
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
P=HERE/'金星计算演示.json'
d=json.loads(P.read_text(encoding='utf-8'))
source=ROOT/'06_原始资料/天文/JPL_Venus_原始返回.json'
raw=json.loads(source.read_text(encoding='utf-8'))['result']
block=raw.split('$$SOE',1)[1].split('$$EOE',1)[0]
line=next(line for line in block.splitlines() if line.strip().startswith('2010-Jul-07 12:40'))
cells=next(csv.reader([line]))
ra,dec,jaz,jalt,last=map(float,cells[3:8])
params=json.loads((ROOT/'06_原始资料/天文/JPL_Venus_参数.json').read_text(encoding='utf-8'))['params']
assert params['SITE_COORD']=="'120.3,30.2,0.01'" and params['APPARENT']=="'AIRLESS'"
assert ra==d['jpl_direct_inputs']['alpha_ra_deg']
assert dec==d['jpl_direct_inputs']['delta_dec_deg']
assert last==d['jpl_direct_inputs']['LAST_decimal_hours']
assert jaz==d['jpl_cross_check_not_calculation_input']['azimuth_deg']
assert jalt==d['jpl_cross_check_not_calculation_input']['altitude_deg']
phi=math.radians(d['query_inputs']['geodetic_latitude_north_deg'])
delta=math.radians(dec)
theta=15*last
hr=(theta-ra+180)%360-180
hour=math.radians(hr)
th=math.radians(theta)
alpha=math.radians(ra)
term1=math.sin(phi)*math.sin(delta)
term2=math.cos(phi)*math.cos(delta)*math.cos(hour)
up=term1+term2
east=-math.cos(delta)*math.sin(hour)
north=math.cos(phi)*math.sin(delta)-math.sin(phi)*math.cos(delta)*math.cos(hour)
alt=math.degrees(math.asin(up))
az=math.degrees(math.atan2(east,north))%360
s=[math.cos(delta)*math.cos(alpha),math.cos(delta)*math.sin(alpha),math.sin(delta)]
z=[math.cos(phi)*math.cos(th),math.cos(phi)*math.sin(th),math.sin(phi)]
eb=[-math.sin(th),math.cos(th),0]
nb=[-math.sin(phi)*math.cos(th),-math.sin(phi)*math.sin(th),math.cos(phi)]
calculated={'phi_deg':math.degrees(phi),'theta_deg':theta,'hour_angle_deg':hr,'term1_sin_phi_sin_delta':term1,'term2_cos_phi_cos_delta_cos_H':term2,'east_component':east,'north_component':north,'up_component_sin_h':up,'altitude_deg':alt,'azimuth_deg':az,'direction_enu_unit_vector':[east,north,up],'target_equatorial_unit_vector':s,'zenith_equatorial_unit_vector':z,'target_dot_zenith':sum(a*b for a,b in zip(s,z))}
errors={}
for key,value in calculated.items():
    previous=d['local_calculation'][key]
    error=max(abs(a-b) for a,b in zip(value,previous)) if isinstance(value,list) else abs(value-previous)
    assert error<1e-12,(key,error)
    errors[key]=error
assert abs(sum(v*v for v in [east,north,up])-1)<1e-14
assert abs(sum(a*b for a,b in zip(s,eb))-east)<1e-14
assert abs(sum(a*b for a,b in zip(s,nb))-north)<1e-14
assert abs(alt-jalt)<1e-8 and abs(az-jaz)<1e-8
d['jpl_direct_inputs']['raw_row']=line
d['local_calculation']['east_basis_equatorial']=eb
d['local_calculation']['north_basis_equatorial']=nb
d['verification']={'status':'passed','checked_against':'保存JPL原始行及本地独立math标量/向量重算','max_saved_scalar_or_vector_difference':max(errors.values()),'field_differences':errors,'unit_vector_squared_length':sum(v*v for v in [east,north,up]),'recomputed_az_deg':az,'recomputed_alt_deg':alt,'difference_from_JPL_printed_az_deg':az-jaz,'difference_from_JPL_printed_alt_deg':alt-jalt,'precision_note':'差值反映同一JPL打印数值的舍入一致性，不是绝对观测精度。','network_requests':0,'paid_api_calls':0,'source_files_modified':False,'sources':[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in d['source_paths']]}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'passed','az':az,'alt':alt,'max_difference':max(errors.values())},ensure_ascii=False))
