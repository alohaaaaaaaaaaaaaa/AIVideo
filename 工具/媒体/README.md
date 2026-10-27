# 通用成片工具

这套工具接收已经审定、已有实音时码的镜头清单，不认识任何特定选题、幕数或人名。它不调用付费接口，不访问网络，不发布视频。新项目的画面、声音、字幕、品牌资产都用相对路径接入。

## 使用

在工作室根目录，用工作室配置好的 Python 环境执行：

```bash
python 工具/媒体/studio_media.py validate 作品/本期/manifest.json
python 工具/媒体/studio_media.py all 作品/本期/manifest.json
```

`all` 按顺序完成 render → verify → player。也可单独使用这三步。`validate`检查输入并输出`导出/检查/输入核验.json`，不编码视频。默认输出1920×1080、25fps、H.264 CRF17、48kHz双声道AAC256k、faststart。

依赖：Python、Pillow、numpy、av(PyAV)、imageio-ffmpeg。FFmpeg必须包含libx264、libass、AAC。macOS采用原片Hiragino Sans GB；无法使用时回退随工作室提供的Noto Sans CJK SC，报告明确披露不同字形。系统字体不复制分发。实际编码log解析libass选中的字体文件与hash，不能把回退冒称原字体完全一致。脚本不依赖旧萧山项目或其虚拟环境。

正式接口：[manifest.schema.json](manifest.schema.json)。最小结构：[manifest.example.json](manifest.example.json)，其中素材名是占位，须换成本期实际文件。可运行的技术示例在[离线测试/manifest.json](离线测试/manifest.json)。`native_label`是人工核验后的声明，不是OCR自动发现。

## manifest约定

- 所有路径相对manifest所在文件夹；允许`../../参考库/...`，不接受绝对路径。`output_dir`默认`导出`。
- `shots`按顺序连接，`duration`必须是整帧时长，25fps时每帧0.04秒。`in`为素材内入点，默认0。`kind`支持`image`、`video`、`ai`、`animation`。
- 源视频原速播放。默认不提取源音轨，最终`audio.path`必须已含需要保留的原声/环境声；防止源片自带BGM和最终BGM重复。禁止`speed!=1`、`loop:true`、超过源时长。AI同一源hash的区间不允许在不同镜头重复使用，复制改名也会拦截。重新转码后的重复需资产台账人工辨认。
- `audio.path`必须是整片48kHz双声道混音，时长与画面差不超过一帧。声音节拍/停顿由声音流程先处理；合成器不拉伸配音、不补长静音、不擅自安排BGM。
- `subtitles`为全片秒数，包含`start/end/text`，最多两行且不重叠。以实音对齐，不能均分字符估计。工具会生成ASS/SRT并烧录。`subtitle_style`可覆盖`font/font_size/margin_v`；默认采用原片Main：Hiragino Sans GB 42px、底距42、描边2.5、阴影1、左右90；`subtitle_style:{profile:"science"}`明确选择底距74。镜头可写`subtitle_style`，单条字幕可写`style`覆盖，优先级为条目＞镜头＞全片。其他分辨率自动缩放默认值；明确指定的值都是当前输出像素。
- `chapters`为`start/title`，第一章从0开始，全部严格递增且小于总时长。章节数不限。
- `source_note`只允许无原生备注的**静态截图**，最多两行。渲染保持已构图fullframe全幅，在y870开始的原版来源区域补这一处栏，必须以`source_note_safe_area:true`确认这里没有需保留正文；绝不因为有来源而把整图缩小。不能再加左上角编辑性备注。网页自身的标题、作者、日期不属于重复备注。
- AI片段必须先在素材里做好一处恰当的情境示意说明，并核验其全时段可读，再写`native_label:true`。合成器只保留，绝不叠第二套。其他动画/视频不接受`source_note`；已有说明照原样。科学动画不需要被一概标为AI画面。
- `watermark`设置PNG路径、像素宽度、x/y、opacity。PNG内已设定的透明度继续有效；不要无故再减弱。每镜头可用`watermark_position:[x,y]`覆盖，数值固定，只在切镜点换位。没有漂浮、弹跳或开头飞入。
- `versions`默认clean和bili；每项有`id/label/watermark`。`watermark:false`仅移除持续品牌水印，**不会删去片尾作者名、证据来源和原生情境说明**。每版可用`watermark_path`换PNG，或`watermark_override:{path,width,x,y,opacity}`整体覆盖。因此可同时导出无水印、B站无账号、抖音账号三个版本。格式/分辨率不同的平台请另用manifest并重新审片，不能直接强裁横屏。

第三版示例：

```json
{"id":"douyin","label":"抖音版","watermark":true,"watermark_path":"../../参考库/品牌/抖音/实际文件名.png"}
```

水印文字不会在编码时重画，始终使用审定PNG。端内作者名与字幕名保持“啊子牙”。TTS对名字的读法另外在声音流程里处理。


## 画面布局必须显式区分

默认`layout:{"mode":"fullframe"}`要求素材已经按输出宽高比构图。1920×1080已排好原文图保持原坐标，来源栏不会触发80%缩放，不裁切真实证据来隐藏黑边。源与目标比例不符时停止，要求先决定构图。

原始网页长图应先由证据工具设计阅读镜头；需要在合成器接入明确节选时，可用`layout:{"mode":"evidence_region","crop":[x,y,width,height],"destination":[x,y,width,height]}`，源crop必须人工确认上下文，目标区域不得越过来源栏。这里是明示裁取阅读段，不能把fill当默认把边裁掉。

`layout:{"mode":"contain","reason":"已审定的完整画幅保留理由"}`才允许完整保留异形素材并留边。没有理由不得使用。它不用于已构图全帧图，不能为了适配新增来源条随意缩画面。

所有默认视觉数值在`默认配置/视觉.json`，以最新1319.96秒采用版核对：来源底栏y870、首行x32/y884/27px，次行y926/23px。视觉配置hash写入渲染记录；变化后verify拒绝拿旧成片过关。

## 输出与重做

默认输出`clean.mp4`、`bili.mp4`、`subtitles.ass`、`subtitles.srt`、`chapters.ffmetadata`、`播放成片.html`。编码用“处理中”文件，完成后才替换正式版本。重做前会把已有输出和字幕/播放器复制到`导出/历史/时间戳/`；源素材完全不改。

`导出/缓存/`含规范化的逐镜头视频、无声画面和共享AAC。两个版本复制同一份AAC，不各自重编，便于核验一致性。调整配音或时间线后必须重新编码，不能只改播放器显示的时间。

`verify`完整解码每版全部视频帧和音频包，检查精确帧数、视频PTS、音画时长、规格、音轨包hash一致性、音频削波、最终AAC实际integrated LUFS/true peak（高于-1dBTP要求修正）、章节数/起点/标题，以及原始输入/字幕/输出hash。每个镜头抽一帧，AI与动画再抽首尾，生成联系表。报告保留`technical_pass_manual_review_required`：这不等于已确认旁白语气、证据真实性或高光对齐。要打开播放器实际试听和检查。

## 真截图原文高光

```bash
python 工具/媒体/evidence_highlight.py 参考库/证据画面/平湖原文高光/高光示例配置.json
```

`image`是原始网页截图或其真实像素裁片；`crop`可选，使用原图像素坐标；`highlights`每项有原图`rect:[左,上,右,下]`、`start`、可选`end/draw_duration`。工具将截图真实像素缩放显示，按旁白时码逐段画下划线，底部只加一处来源。它不会把正文重新打字伪装成网页。输出MP4、首中尾PNG和含来源hash的JSON。接入成片时用`kind:animation,native_label:true`，不要再填`source_note`。

生成高光的时间码需根据真实语音来定；示例8秒是演示，不是别的题材通用节拍。截图原页、原文、URL、发布时间、截取日期/方式要保存在本期证据台账。裁取片段不得改变上下文含义。换题时必须换为该题真实原文。

## 离线回归

```bash
python 工具/媒体/smoke_test.py
```

生成6秒3镜头、两种版本的合成技术短片，验证完整解码、实际烧录字幕像素、水印差异和5种错误拦截。测试素材明确是流程测试，**不是美术模板，也不代表工作室视频应采用测试图样式**。无需API费用。
