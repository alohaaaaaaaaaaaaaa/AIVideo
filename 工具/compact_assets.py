"""Byte-exact content-addressed assets; standard library only, no network or API.
Inline previews stay playable. Managed originals are restored at their old paths.
"""
from pathlib import Path,PurePosixPath
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,lzma,os,re,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
INDEX='资源存储/资源清单.json'
EXCLUDE_DIRS={'.venv','.git','__pycache__','缓存','历史','node_modules','资源存储'}
EXCLUDE_NAMES={'.DS_Store','credentials.json','ky.json','.compact_state.json'}
GENERATED_REPORTS={'检查/精简打包核验.json'}
IGNORE_BEGIN='# BEGIN AZIYAH COMPACT MANAGED ASSETS'
IGNORE_END='# END AZIYAH COMPACT MANAGED ASSETS'
TEXT_EXT={'.py','.md','.txt','.json','.html','.css','.js','.yaml','.yml','.toml','.ini','.cfg','.csv','.ass','.srt','.xml','.log','.ffmetadata','.ffconcat','.code-workspace'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def safe(root,rel):
 pp=PurePosixPath(rel)
 if pp.is_absolute() or '..' in pp.parts or not pp.parts or '\\' in rel:raise ValueError('Unsafe asset path')
 path=Path(root).joinpath(*pp.parts)
 cur=Path(root)
 for part in pp.parts:
  cur=cur/part
  if cur.is_symlink():raise ValueError('Symlink in asset path: '+rel)
 if not path.resolve().is_relative_to(Path(root).resolve()):raise ValueError('Asset escaped root')
 return path

def shuffle4(b):return b[0::4]+b[1::4]+b[2::4]+b[3::4]
def unshuffle4(b):
 n=len(b);out=bytearray(n);pos=0
 for i in range(4):
  count=(n+3-i)//4;out[i::4]=b[pos:pos+count];pos+=count
 return bytes(out)
def decode(root,obj):
 path=safe(root,obj['path'])
 if sha(path)!=obj['stored_sha256']:raise ValueError('Stored object changed: '+obj['path'])
 b=path.read_bytes();codec=obj['codec']
 if codec.startswith('xz'):b=lzma.decompress(b)
 if codec=='xz-shuffle4':b=unshuffle4(b)
 elif codec not in ('raw','xz'):raise ValueError('Unknown codec')
 if len(b)!=obj['original_bytes'] or hashlib.sha256(b).hexdigest()!=obj['original_sha256']:raise ValueError('Restored bytes mismatch')
 return b

def restore(root=ROOT):
 root=Path(root).resolve();idx=root/INDEX
 if not idx.exists():return {'compact':False,'restored':0}
 m=json.loads(idx.read_text('utf-8'));groups={}
 # Resolve all paths before performing any writes.
 for row in m['files']:
  target=safe(root,row['path'])
  if row['storage']=='asset' and not target.exists():groups.setdefault(row['sha256'],[]).append(row)
  elif target.exists() and not target.is_file():raise ValueError('Target is not a file: '+row['path'])
 for obj in m['objects'].values():safe(root,obj['path'])
 count=0
 for h,rows in groups.items():
  data=decode(root,m['objects'][h])
  for row in rows:
   target=safe(root,row['path']);target.parent.mkdir(parents=True,exist_ok=True)
   fd,tmp=tempfile.mkstemp(prefix='.asset-',dir=target.parent)
   try:
    with os.fdopen(fd,'wb') as f:f.write(data)
    if sha(tmp)!=h:raise ValueError('Disk write hash mismatch')
    # Hard-link publishes atomically without replacing an existing/user-edited file.
    try:os.link(tmp,target)
    except FileExistsError:pass
    else:count+=1
   finally:Path(tmp).unlink(missing_ok=True)
 return {'compact':True,'restored':count,'existing_files':'preserved; run verify for exact-content check'}

def verify(root=ROOT,require_restored=False):
 root=Path(root).resolve();m=json.loads((root/INDEX).read_text('utf-8'));bad=[];objects=0;restored=0
 for h,obj in m['objects'].items():
  if obj['original_sha256']!=h:raise ValueError('Object key mismatch')
  decode(root,obj);objects+=1
 for row in m['files']:
  p=safe(root,row['path'])
  if p.exists():
   if sha(p)!=row['sha256']:bad.append(row['path'])
   else:restored+=1
  elif row['storage']=='inline' or require_restored:bad.append(row['path'])
 report={'status':'passed' if not bad else 'failed','files':len(m['files']),'objects_fully_decoded':objects,'present_original_hashes_matched':restored,'required_full_restore':require_restored,'mismatches':bad}
 if bad:raise ValueError(json.dumps(report,ensure_ascii=False))
 return report

def build(source,destination,keep_path=None):
 source=Path(source).resolve();dest=Path(destination).resolve()
 if dest.exists():raise FileExistsError('Keep existing destination: '+str(dest))
 if dest.is_relative_to(source):raise ValueError('Compact output must be outside source')
 # Building from an already compact working copy also captures its restored originals.
 restore(source)
 keep=set(json.loads(Path(keep_path or source/'默认配置/精简版预览保留.json').read_text('utf-8')))
 source_rows=[]
 for p in sorted(source.rglob('*')):
  rel=p.relative_to(source)
  if rel.as_posix() in GENERATED_REPORTS:continue
  if any(x in EXCLUDE_DIRS for x in rel.parts):continue
  if p.name in EXCLUDE_NAMES or p.name.startswith('.env') or p.name.endswith(('.tar.gz','_处理中.mp4')) or p.suffix.lower() in {'.pyc','.zip','.7z','.tar','.tmp','.pem','.key','.p12','.pfx'}:continue
  if p.is_symlink():raise ValueError('Source symlink: '+str(rel))
  if p.is_file():
   name=rel.as_posix();n=p.stat().st_size
   inline=name in keep or n<65536 or p.suffix.lower() in TEXT_EXT or p.name.startswith('.')
   if p.suffix.lower() in {'.log','.lock'}:inline=False
   source_rows.append({'path':name,'bytes':n,'sha256':sha(p),'storage':'inline' if inline else 'asset'})
 source_bytes=sum(r['bytes'] for r in source_rows)
 dest.mkdir(parents=True);(dest/'资源存储/objects').mkdir(parents=True)
 objects={};rows=[]
 for row in source_rows:
  if row['storage']=='inline':
   target=safe(dest,row['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/row['path'],target)
  rows.append(row)
 by_hash={}
 for row in rows:
  if row['storage']=='asset':by_hash.setdefault(row['sha256'],row)
 def pack(item):
  h,row=item;b=(source/row['path']).read_bytes()
  codec='xz-shuffle4' if Path(row['path']).suffix.lower()=='.wav' else 'xz'
  encoded=lzma.compress(shuffle4(b) if codec=='xz-shuffle4' else b,preset=6)
  if len(encoded)>=len(b):encoded=b;codec='raw'
  path='资源存储/objects/'+h+('.xz' if codec.startswith('xz') else '.blob')
  (dest/path).write_bytes(encoded)
  obj={'path':path,'codec':codec,'stored_bytes':len(encoded),'stored_sha256':hashlib.sha256(encoded).hexdigest(),'original_bytes':len(b),'original_sha256':h}
  assert decode(dest,obj)==b
  return h,obj
 with ThreadPoolExecutor(max_workers=3) as pool:
  for i,(h,obj) in enumerate(pool.map(pack,by_hash.items()),1):
   objects[h]=obj
   if i%40==0:print('已无损压缩并核验',i,'/',len(by_hash),flush=True)
 ignore=dest/'.gitignore';s=ignore.read_text('utf-8') if ignore.exists() else ''
 # Only replace our own generated block; preserve user-authored ignore policy.
 s=re.sub(re.escape(IGNORE_BEGIN)+r'.*?'+re.escape(IGNORE_END)+r'\n?', '', s, flags=re.S)
 s=s.rstrip()+'\n\n'+IGNORE_BEGIN+'\n'
 for row in rows:
  if row['storage']=='asset':
   # Escape gitignore pattern metacharacters in literal asset paths.
   rel=row['path'];rel=''.join('\\'+c if c in '\\*?[]!#' else c for c in rel)
   s+='/'+rel+'\n'
 s+=IGNORE_END+'\n'
 ignore.write_text(s,encoding='utf-8')
 for row in rows:
  if row['path']=='.gitignore':row['source_sha256']=row['sha256'];row['sha256']=sha(ignore);row['bytes']=ignore.stat().st_size
 m={'schema_version':1,'created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'source_folder_name':source.name,'excludes':sorted(EXCLUDE_DIRS|EXCLUDE_NAMES),'preservation':'All selected adopted source files preserved exactly, except generated .gitignore additions; no lossy media change','files':rows,'objects':objects}
 save(dest/INDEX,m)
 with tempfile.TemporaryDirectory(prefix='aziyah-pack-gitcheck-') as td:
  gd=Path(td)/'index.git';subprocess.run(['git','init','--bare','--quiet',str(gd)],check=True,capture_output=True)
  paths=[r['path'] for r in rows if r['storage']=='inline']+[o['path'] for o in objects.values()]+[INDEX]
  checked=subprocess.run(['git','--git-dir='+str(gd),'--work-tree='+str(dest),'check-ignore','--no-index','--stdin','-z'],input=b'\0'.join(x.encode() for x in paths)+b'\0',capture_output=True,cwd=dest)
  if checked.returncode not in (0,1):raise RuntimeError('Git tracking check failed')
  if checked.stdout:raise ValueError('Required files are ignored: '+repr(checked.stdout.decode().split('\0')[:-1]))
 report=verify(dest);report.update(source_bytes=source_bytes,source_files=len(rows),stored_bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()),kept_preview_files=len(keep),unique_stored_objects=len(objects),all_objects_under_50MiB=all(o['stored_bytes']<50*2**20 for o in objects.values()),lossy_conversion=False)
 save(dest/'检查/精简打包核验.json',report);print(json.dumps(report,ensure_ascii=False,indent=2));return report

def main():
 p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='action',required=True)
 a=sp.add_parser('build');a.add_argument('--source',type=Path,default=ROOT);a.add_argument('--output',type=Path,required=True);a.add_argument('--keep',type=Path)
 for name in ('restore','verify'):
  a=sp.add_parser(name);a.add_argument('--root',type=Path,default=ROOT)
  if name=='verify':a.add_argument('--require-restored',action='store_true')
 a=p.parse_args()
 if a.action=='build':build(a.source,a.output,a.keep)
 elif a.action=='restore':print(json.dumps(restore(a.root),ensure_ascii=False))
 else:print(json.dumps(verify(a.root,a.require_restored),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
