"""新工作室中检查五个独立引擎及静态输出；不触及旧项目或付费接口。"""
from pathlib import Path
import importlib.util,json,hashlib,platform
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]

def main():
    check=ROOT/'参考库/动画/检查';check.mkdir(exist_ok=True)
    examples=[('星月范例','sky','below',.8),('日期范例','calendar','timezone',.8),('曝光范例','exposure','inspect',.8),('雷达范例','radar',None,22),('汇聚范例','convergence','messages',9.7)]
    images=[];results=[]
    for filename,key,phase,p in examples:
        path=ROOT/'工具/动画'/f'{filename}.py';spec=importlib.util.spec_from_file_location(key,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        if key in ['sky','exposure']:im=m.frame(phase=phase,p=p,captions=False)
        elif key=='calendar':im=m.frame(phase,p,captions=False)
        elif key=='radar':im=m.frame(p,captions=False)
        else:im=m.frame(phase,p,13.04)
        assert im.mode=='RGB' and im.size in [(1280,720),(1920,1080)]
        target=check/f'{filename}_独立调用.png';im.save(target);images.append((filename,im))
        results.append({'engine':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'frame_rendered','size':im.size,'image':str(target.relative_to(ROOT))})
    sheet=Image.new('RGB',(1280,3*390),(7,13,21));d=ImageDraw.Draw(sheet);font=ImageFont.truetype(str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf'),20)
    for i,(name,im) in enumerate(images):
        x=i%2*640;y=i//2*390;sheet.paste(im.resize((640,360)),(x,y));d.text((x+15,y+362),name,font=font,fill='#dbe9ee')
    sheet.save(check/'独立五引擎联系表.jpg',quality=95)
    report={'status':'five_engines_render_passed_visual_review_pending','runtime_python':platform.python_version(),'runtime_scope':'当前工作室路径解析','old_project_imports':0,'engines':results}
    (check/'五引擎调用核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
