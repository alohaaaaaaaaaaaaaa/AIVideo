"""Create a portable studio backup, preserving original assets and excluding local secrets/env/cache."""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED_DIRS={'.venv','__pycache__','.git','缓存','历史','node_modules'}
EXCLUDED_NAMES={'.DS_Store','ky.json','credentials.json','归档记录.json'}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path)
    a=ap.parse_args();stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    target=(a.output or ROOT.parent/f'啊子牙视频工作室_备份_{stamp}.zip').resolve()
    if target.exists():raise FileExistsError('Preserve existing archive: '+str(target))
    managed=set()
    compact_index=ROOT/'资源存储/资源清单.json'
    if compact_index.exists():
        from compact_assets import verify
        verify(ROOT)
        compact=json.loads(compact_index.read_text('utf-8'))
        managed={r['path'] for r in compact['files'] if r['storage']=='asset'}
    files=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if rel.as_posix() in managed:continue
        if any(x in EXCLUDED_DIRS for x in rel.parts):continue
        excluded_name=p.name in EXCLUDED_NAMES
        if compact_index.exists() and p.name=='归档记录.json':excluded_name=False
        if excluded_name or p.name.startswith('.env') or p.suffix in {'.pyc','.zip','.tmp'}:continue
        if p.is_symlink():raise ValueError('Archive needs actual file, not symlink: '+str(rel))
        if p.is_file():files.append((p,rel))
    rows=[{'path':str(rel),'bytes':p.stat().st_size,'sha256':sha(p)} for p,rel in files]
    metadata={'created_at':datetime.now().isoformat(timespec='seconds'),'root_folder':ROOT.name,'files':rows,
              'compact_managed_originals_stored_as_objects':bool(compact_index.exists()),
              'excludes':sorted(EXCLUDED_DIRS|EXCLUDED_NAMES),'credentials_included':False,
              'restore':'Extract folder; rebuild .venv using 工具/bootstrap.py; configure credentials outside project on a new computer.'}
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for p,rel in files:z.write(p,str(Path(ROOT.name)/rel))
        z.writestr(ROOT.name+'/归档文件清单.json',json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(target) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('ZIP CRC failed: '+bad)
    report={'archive':str(target),'archive_sha256':sha(target),'archive_bytes':target.stat().st_size,
            'files':len(files),'uncompressed_bytes':sum(r['bytes'] for r in rows),'zip_crc':'passed',
            'credentials_included':False,'venv_included':False,'embedded_inventory':'归档文件清单.json'}
    report_path=ROOT/('检查/最新精简归档记录.json' if compact_index.exists() else '检查/归档记录.json')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
