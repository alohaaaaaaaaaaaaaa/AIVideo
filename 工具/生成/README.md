# AI视频工具接口

`video.py`只实现已核官方文档的MiniMax v1 T2V。依赖requests、av；不读取旧项目凭据。模型默认`MiniMax-Hailuo-02`，可在兼容v1名单内改配置。旧型号和旧3.5元价格不保证当期可用；详情见`文档/06_AI画面与任务管理.md`。

## 计划与提交

```bash
python 工具/生成/video.py plan --input 作品/本期/AI镜头任务.json --output 作品/本期/AI生成计划.json
python 工具/生成/video.py submit --plan 作品/本期/AI生成计划.json --output 作品/本期/AI任务 --authorization 作品/本期/AI生成授权.json --budget-cny 具体子预算
python 工具/生成/video.py query --receipt 作品/本期/AI任务/receipts/请求hash.json
python 工具/生成/video.py download --receipt 作品/本期/AI任务/receipts/请求hash.json --output 作品/本期/素材/N001_原片.mp4
```

plan参数：`--input/--output`必填；`--config`可选；`--rate-cny-per-video`默认3.5（历史估算）。submit另可`--only N001 N002`；具体budget数值不能照抄示例。query/download不会创建新生成任务。不要把query失败当作submit重试理由。

输入示例`shots.example.json`：顶层`config`可覆盖provider/base_url/model/duration/resolution/prompt_optimizer/aigc_watermark；shots每条包含id、purpose、prompt、acceptance、context_label，可用request_override覆盖本镜头model/duration/resolution/prompt_optimizer/aigc_watermark，estimated_cost_cny可指定估算。模型/规格需在已验证v1集合中；其他provider明确拒绝。

授权示例`authorization.example.json`默认未批准。字段包括：approved、plan_sha256、approval_reference、scope、approved_shot_ids、budget_cap_cny、max_new_tasks、price_basis。price_basis含verified_for_this_plan、checked_at、source_url、evidence_file（相对授权文件）、evidence_sha256、unit_prices_cny（按镜头ID）。已有会话授权足够覆盖时引用它，不要为了填表额外问用户。示例不能被直接改成true然后冒充真实授权。

输出任务目录保存`receipts/<request-hash>.json`与`ledger.json`。每份receipt在POST前就存在，记录精确body、hash、估算、状态、task_id/file_id及下载hash。目录有提交锁，避免两个进程同时超支或重复发同一请求。缺task_id的已尝试请求一律不自动重发；有task_id的请求只查和下载。

本期视频子预算由此目录独立计数；如与TTS共享总预算，由工作室总台账分别分配上限并汇总。费用字段兼容TTS的`estimated_total_cny`、`estimated_cost_cny`、`price_basis`、`billing_verified`，不把估算冒称真实账单。

## 情境标识只加一次

先实际查看原片确认没有既有说明，再执行：

```bash
python 工具/生成/label_context.py --input 作品/本期/素材/N001_原片.mp4 --output 作品/本期/素材/N001_采用.mp4 --text '情境示意' --confirmed-unlabeled
```

已有原生说明不执行这步。原片不覆盖，输出另存.context.json记录，主合成写native_label:true。此脚本不更改速度/时长，保留原声但最终混音是否使用由声音流程显式决定。仍要抽首中尾看标签是否清楚、不遮主体。

## 本轮离线测试

```bash
python 工具/生成/test_video_offline.py
```

依赖同工作室`工具/媒体/离线测试/导出/clean.mp4`作本地模拟下载内容；如缺失先运行媒体smoke_test.py。假HTTP客户端不会联网，密钥函数只返回测试字符串，临时mock授权不能用于真实API。结果保存`离线状态机测试.json`。

API真实连通、账号型号可用性与真实扣费**未在本轮测试**。官方契约只读核实且本轮付费0。新增v2/provider适配前必须核对认证、请求结构、异步状态、费用、重试语义与下载协议，不能仅替换URL。
