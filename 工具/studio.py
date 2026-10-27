"""Small local entry point for Codex. Users can work entirely in natural language."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, hashlib, importlib.util, json, os, re, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def credentials():
    env=os.environ.copy()
    if sys.platform=='darwin':base=Path.home()/'Library/Application Support/啊子牙视频工作室'
    else:base=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'aziyah-video'
    p=base/'credentials.json'
    if p.is_file():
        d=read(p)
        for key in ['MINIMAX_API_KEY']:
            if not env.get(key) and isinstance(d.get(key),str):env[key]=d[key]
    return env
def run(path,args,secret=False):
    env=credentials() if secret else os.environ.copy()
    subprocess.run([sys.executable,str(ROOT/path),*args],cwd=ROOT,env=env,check=True)
def doctor():
    names=['numpy','PIL','scipy','soundfile','av','imageio_ffmpeg','requests','jsonschema','yaml']
    modules={name:importlib.util.find_spec(name) is not None for name in names}
    paths=['默认配置/声音.json','工具/媒体/studio_media.py','工具/声音/score_mix.py','工具/动画/渲染范例.py',
      '参考库/动画/字体/NotoSansCJKsc-Regular.otf','参考库/品牌/B站/透明PNG/啊子牙_悠哉_B站无账号_1080p.png']
    assets={s:(ROOT/s).is_file() for s in paths};ffmpeg=False
    if modules['imageio_ffmpeg']:
        import imageio_ffmpeg
        ffmpeg=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-version'],capture_output=True).returncode==0
    report={'checked_at':now(),'python':sys.version.split()[0],'environment_is_local':Path(sys.prefix).resolve()==(ROOT/'.venv').resolve(),
      'modules':modules,'essential_assets':assets,'ffmpeg_available':ffmpeg,'api_credential_available':bool(credentials().get('MINIMAX_API_KEY')),
      'credential_value_logged':False,'paid_api_connectivity_tested':False,'paid_calls':0}
    report['status']='passed' if all(modules.values()) and all(assets.values()) and ffmpeg else 'dependencies_missing'
    save(ROOT/'检查/环境检查.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['status']!='passed':raise SystemExit(2)
def new(title,output=None):
    clean=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title).strip('. ')[:80]
    if not clean:raise ValueError('Title is empty')
    dest=Path(output).expanduser().resolve() if output else ROOT/'作品'/(now()[:10]+'_'+clean)
    if dest.exists():raise FileExistsError('Existing episode preserved; open its 状态.json instead: '+str(dest))
    shutil.copytree(ROOT/'模板/单期项目',dest)
    project=read(dest/'项目.json');project.update(title=title,created_at=now(),studio_root=os.path.relpath(ROOT,dest))
    save(dest/'项目.json',project)
    for folder in ['01_调查/原始资料','02_剧本','03_声音','04_素材/真实证据','04_素材/AI情境','04_素材/动画','05_剪辑','06_导出','07_检查','08_归档','生成记录']:(dest/folder).mkdir(parents=True,exist_ok=True)
    # No assets are invented. This manifest is intentionally not renderable until real media exists.
    manifest=read(dest/'manifest.json');manifest['title']=title
    defaults=read(ROOT/'默认配置/工作室.json');logo=ROOT/defaults['brand']['bili_watermark']
    manifest['watermark']['path']=os.path.relpath(logo,dest)
    save(dest/'manifest.json',manifest)
    (dest/'00_本期任务.md').write_text(f'# {title}\n\n当前：等待明确题目/调查范围。请用自然语言告诉Codex要查什么；不要为填表而要求用户学习制作。\n\n读取本期项目与状态，再按工作室技能推进。默认南方小哥与既定BGM，先完整声画稿；本期制作授权和预算以真实对话为准。\n')
    save(ROOT/'当前项目.json',{'path':os.path.relpath(dest,ROOT),'title':title,'updated_at':now()})
    print(json.dumps({'created':str(dest),'paid_calls':0},ensure_ascii=False))
def source(episode,file,ident,url,title,published,kind):
    ep=Path(episode).resolve();src=Path(file).resolve();assert src.is_file()
    assert re.fullmatch(r'[A-Za-z0-9_-]+',ident),'Source id should be E001 etc.'
    p=ep/'01_调查/来源登记.json';data=read(p);assert not any(x['id']==ident for x in data['sources'])
    dest=ep/'01_调查/原始资料'/f'{ident}_{src.name}';dest.parent.mkdir(parents=True,exist_ok=True)
    assert not dest.exists();shutil.copy2(src,dest)
    data['sources'].append({'id':ident,'title':title,'url':url,'published_at':published,'saved_at':now(),'type':kind,
      'local_file':str(dest.relative_to(ep)),'sha256':sha(dest),'relation_to_claims':[],'limits':'待核对完整上下文','rights_or_use_basis':'待记录'})
    save(p,data);print(json.dumps({'source':ident,'stored':str(dest),'sha256':sha(dest)},ensure_ascii=False))
def snapshot(episode,label):
    ep=Path(episode).resolve();label=re.sub(r'[^\w\-\u3400-\u9fff]','_',label)
    dest=ep/'08_归档'/(now().replace(':','-')+'_'+label);dest.mkdir(parents=True,exist_ok=False)
    files=[]
    for folder in ['01_调查','02_剧本','03_声音','05_剪辑','生成记录']:
        for p in (ep/folder).rglob('*'):
            if p.is_file() and p.suffix in {'.json','.md','.txt','.srt','.ass','.ffmetadata'}:files.append(p)
    files += [p for p in ep.iterdir() if p.is_file() and p.suffix in {'.json','.md'}]
    rows=[]
    for p in files:
        rel=p.relative_to(ep);target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);rows.append({'path':str(rel),'sha256':sha(p)})
    save(dest/'快照.json',{'at':now(),'files':rows,'media_policy':'Snapshot freezes plans and metadata; preserve/revise media under new names.'})
    print(str(dest))
def main():
    from compact_assets import restore
    restored=restore(ROOT)
    if restored.get('restored'):print('已校验并恢复精简版原件：',restored['restored'],flush=True)
    # Pass-through commands preserve the documented child CLI without duplicating schemas.
    routes={'render':('工具/媒体/studio_media.py',False),'audio':('工具/声音/score_mix.py',False),
      'tts':('工具/声音/tts.py',True),'voice':('工具/声音/prepare_voice.py',False),'assemble':('工具/声音/assemble_voice.py',False),'bridge':('工具/声音/bridge.py',False),
      'audio-film':('工具/声音/score_film.py',False),'storyboard':('工具/导演/compile_storyboard.py',False),
      'webpage-capture':('工具/网页/capture_evidence.py',False),'webpage-animate':('工具/网页/animate_evidence.py',False),'webpage-audit':('工具/网页/audit_capture.py',False),
      'animation':('工具/动画/渲染范例.py',False),'highlight':('工具/媒体/evidence_highlight.py',False),'video':('工具/生成/video.py',True)}
    if len(sys.argv)>1 and sys.argv[1] in routes:
        path,secret=routes[sys.argv[1]];run(path,sys.argv[2:],secret);return
    ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='action',required=True)
    sp.add_parser('doctor');p=sp.add_parser('new');p.add_argument('title');p.add_argument('--output')
    p=sp.add_parser('snapshot');p.add_argument('episode');p.add_argument('label')
    p=sp.add_parser('source');p.add_argument('episode');p.add_argument('file');p.add_argument('--id',required=True);p.add_argument('--url',required=True);p.add_argument('--title',required=True);p.add_argument('--published',default='');p.add_argument('--kind',default='original')
    a=ap.parse_args()
    if a.action=='doctor':doctor()
    elif a.action=='new':new(a.title,a.output)
    elif a.action=='snapshot':snapshot(a.episode,a.label)
    elif a.action=='source':source(a.episode,a.file,a.id,a.url,a.title,a.published,a.kind)
if __name__=='__main__':main()
