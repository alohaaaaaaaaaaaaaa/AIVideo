"""Create this studio's Python environment. No editing application is needed."""
from pathlib import Path
import argparse, subprocess, sys, venv

ROOT=Path(__file__).resolve().parents[1]
def main():
    from compact_assets import restore
    result=restore(ROOT)
    if result.get('restored'):print('已校验并恢复精简版原件：',result['restored'])
    p=argparse.ArgumentParser();p.add_argument('--optional',action='store_true');a=p.parse_args()
    if sys.version_info<(3,11):raise SystemExit('Use Python 3.11 or newer (tested with 3.13). Codex should locate/install it before retrying.')
    target=ROOT/'.venv'
    if not (target/'pyvenv.cfg').exists():venv.EnvBuilder(with_pip=True).create(target)
    py=target/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    req=ROOT/('requirements.lock.txt' if (ROOT/'requirements.lock.txt').exists() else 'requirements.txt')
    subprocess.run([str(py),'-m','pip','install','-r',str(req)],check=True)
    if a.optional:subprocess.run([str(py),'-m','pip','install','-r',str(ROOT/'requirements-optional.txt')],check=True)
    subprocess.run([str(py),str(ROOT/'工具/studio.py'),'doctor'],check=True)
if __name__=='__main__':main()
