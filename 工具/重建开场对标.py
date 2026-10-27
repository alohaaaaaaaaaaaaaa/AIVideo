"""Rebuild the continuous adopted opening locally; archival inputs are explicit."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'参考库/原片同段对标/开场29秒'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
    audio=ROOT/'参考库/声音/开场连续29秒对标/最终/开场29.36_默认混音_48k_stereo.wav'
    t=json.loads((ROOT/'参考库/声音/开场连续29秒对标/timeline.json').read_text())
    t.update(frames=734,chapters=[{'start':0,'title':'网友已经开始卖船票了'}])
    save(BASE/'实音时间线.json',t)
    rows=json.loads((BASE/'镜头与采用时码.json').read_text())['shots']
    locked=json.loads((BASE/'输入/采用素材锁定.json').read_text())
    for item in locked['assets']:
        asset=(BASE/item['path']).resolve()
        if sha(asset)!=item['asset_sha256']:
            raise ValueError('参考素材已变更，先重新检查实际画面并记录采用，不自动更新验收: '+item['id'])
    intentions=[
      ('读出作者、日期与船票包袱；红线跟随诺亚飞舟和要票原词','以真实笑评兑现标题中的当年网友'),
      ('看到机场夜景，听懂停航与卖票笑话的反差','从玩笑回到事件背景；情境示意只保留原生一处'),
      ('读出另一位网友声称私人飞机；看到转述尚未独立证实','从笑评转到可追查但尚不能采信的说法'),
      ('认出央视经济半小时转载标题、日期与原文来源','说明调查还找到另一层材料，不能把留言当报道'),
      ('看到网页查找定位动作，不把动效当证据本身','从来源身份进入相关报道段落'),
      ('同时辨认日期、机场与私人飞机原文上下文','核对它谈的是不是同一事件'),
      ('回看留言并听清接下来要查什么','让观众带着问题进入下一章'),
      ('短留拍承接下一章音乐；不新增无任务动作','保留原采用版章尾0.4秒和跨章音乐桥尾')]
    shots=[]
    for i,(r,(task,reason)) in enumerate(zip(rows,intentions,strict=True)):
        asset=(ROOT/'参考库/网页取证/开场评论/首镜5.32秒_实音划线_完整来源.mp4') if i==0 else BASE/r['path']
        seg=t['segments'][r['paragraph_index']]
        row={'id':r['id'] if i!=7 else 'F01_04_TAIL','paragraph_id':seg['id'],
          'start_offset':round(r['start']-seg['start'],8),'end_offset':round(r['end']-seg['start'],8),
          'kind':'ai' if i==1 else 'animation' if i in (0,3,4) else 'video','path':os.path.relpath(asset,BASE),
          'asset_sha256':sha(asset),'native_label':True,'layout':{'mode':'fullframe'},'viewer_task':task,'transition_reason':reason,
          'source_ids':['天涯评论归档'] if i in (0,2,6,7) else ['AI情境'] if i==1 else ['央视节目实录_新浪转载'],
          'watermark_position':[1664,40] if i in (0,1,2,6,7) else [1664,950]}
        if i==1:
            receipt=BASE/'输入/机场情境_采用核对.json'
            review=json.loads(receipt.read_text())
            if review.get('status')!='accepted' or review.get('asset_sha256')!=sha(asset):
                raise ValueError('机场情境片段不再匹配已完成的画面核对')
            row['acceptance_record']=os.path.relpath(receipt,BASE)
        shots.append(row)
    plan={'schema_version':1,'title':'啊子牙 · 开场29秒原片标准复核','timeline':'实音时间线.json','timeline_sha256':sha(BASE/'实音时间线.json'),
      'audio':os.path.relpath(audio,BASE),'audio_sha256':sha(audio),'output_dir':'导出','shots':shots,
      'delivery':{'width':1920,'height':1080,'subtitle_style':{'profile':'main'}}}
    save(BASE/'声画任务.json',plan)
    for args in [('storyboard','--plan',str(BASE/'声画任务.json'),'--output',str(BASE/'manifest.json')),('render','all',str(BASE/'manifest.json'))]:
        subprocess.run([sys.executable,str(ROOT/'工具/studio.py'),*args],cwd=ROOT,check=True)
if __name__=='__main__':main()
