> ## Documentation Index
> Fetch the complete documentation index at: https://platform.minimaxi.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# 定价概览

[定价概览](#overview)

模型价格

[语言模型](#models/text)
[视频](#models/video)
[语音](#models/speech)
[图像](#models/image)
[音乐](#models/music)

工具价格

[MCP](#tools/mcp)
[服务端工具](#tools/tools)

资源包

[语音资源包](#packages/speech)
[视频资源包](#packages/video)

计费指南

[付费方式对比](#guides/compare)
[按量计费说明](#guides/billing)
[资源包使用规则](#guides/packages)
[常见问题](#guides/faq)

> **定价目录**
>
> [定价概览](#overview)
>
> 模型价格
>
> [语言模型](#models/text)
> [视频](#models/video)
> [语音](#models/speech)
> [图像](#models/image)
> [音乐](#models/music)
>
> 工具价格
>
> [MCP](#tools/mcp)
> [服务端工具](#tools/tools)
>
> 资源包
>
> [语音资源包](#packages/speech)
> [视频资源包](#packages/video)
>
> 计费指南
>
> [付费方式对比](#guides/compare)
> [按量计费说明](#guides/billing)
> [资源包使用规则](#guides/packages)
> [常见问题](#guides/faq)

查看 MiniMax 开放平台的模型与工具价格，选购语音、视频资源包，或了解计费规则。

## 语言模型

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

| **模型** | **输入价格**  元/百万 tokens | **输出价格**  元/百万 tokens | **缓存读取**  元/百万 tokens |
| :- | :-: | :-: | :-: |
| **MiniMax-M3.1-Flash** | 1.00 | 4.00 | 0.10 |

**标准**

| **模型** | **输入价格**  元/百万 tokens | **输出价格**  元/百万 tokens | **缓存读取**  元/百万 tokens |
| :- | :-: | :-: | :-: |
| **MiniMax-M3** ≤ 512k 输入 tokens 永久五折 | ~~4.20~~ 2.10 | ~~16.80~~ 8.40 | ~~0.84~~ 0.42 |
| **MiniMax-M3** > 512k 输入 tokens\* 永久五折 | ~~8.40~~ 4.20 | ~~33.60~~ 16.80 | ~~1.68~~ 0.84 |

**优先**\*

| **模型** | **输入价格**  元/百万 tokens | **输出价格**  元/百万 tokens | **缓存读取**  元/百万 tokens |
| :- | :-: | :-: | :-: |
| **MiniMax-M3** ≤ 512k 输入 tokens 永久五折 | ~~6.30~~ 3.15 | ~~25.20~~ 12.60 | ~~1.26~~ 0.63 |
| **MiniMax-M3** > 512k 输入 tokens 永久五折 | ~~12.60~~ 6.30 | ~~50.40~~ 25.20 | ~~2.52~~ 1.26 |

\* 优先服务可让请求获得优先准入，从而更快响应并降低失败率。调用时将 `service_tier` 设为 `priority` 即可启用。该层级按标准价格的 1.5 倍计费。

> [!NOTE]
>
> 请注意：
>
> 1. 计费项是token数；tokens字符比值根据使用场景的不同略有浮动，以实际消耗为准，字符数包括标点等
> 2. Token与字符比（估算）：1600 中文字符约消耗 1000 tokens

## 视频

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

### H3 系列旗舰模型

<table>
  <thead>
    <tr>
      <th>模型</th>
      <th>输出分辨率</th>
      <th>输出视频\
      每秒</th>
      <th>输入视频\
      每秒</th>
      <th>输入图片\
      每张\
      超出免费额度后</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td rowSpan="2">**MiniMax-H3**\
      画质优先，适合高品质视频创作</td>
      <td>2K</td>
      <td>¥0.80</td>
      <td>¥0.80</td>
      <td>¥0.20</td>
    </tr>

    <tr>
      <td>768P</td>
      <td>¥0.50</td>
      <td>¥0.50</td>
      <td>¥0.20</td>
    </tr>

    <tr>
      <td>**MiniMax-H3-Highspeed**\
      兼顾质量与速度，适合日常内容创作</td>
      <td>768P</td>
      <td>¥0.40</td>
      <td>¥0.40</td>
      <td>¥0.20</td>
    </tr>

    <tr>
      <td rowSpan="2">**MiniMax-H3-Lite**\
      更低的成本，适合创意尝试与批量生成</td>
      <td>768P</td>
      <td>¥0.26</td>
      <td>¥0.26</td>
      <td>¥0.13</td>
    </tr>

    <tr>
      <td>480P</td>
      <td>¥0.16</td>
      <td>¥0.16</td>
      <td>¥0.13</td>
    </tr>
  </tbody>
</table>

* **图片输入**：每次任务前 **5 张**免费，超出部分按张计费；单价不随图片或输出视频分辨率变化。
* **视频输入**：按输入时长及所选模型的输出分辨率计费。
* **任务类型**：同一模型、同一分辨率下，各任务类型单价相同；音频输入免费。

> **查看旗舰模型任务类型**
>
> <table>
>   <thead>
>     <tr>
>       <th>模型</th>
>       <th>文生 t2v</th>
>       <th>图生 i2v</th>
>       <th>首尾帧 fl2v</th>
>       <th>参考生 ref</th>
>     </tr>
>   </thead>
>
>   <tbody>
>     <tr>
>       <td>MiniMax-H3</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>图片、视频、音频</td>
>     </tr>
>
>     <tr>
>       <td>MiniMax-H3-Highspeed</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>图片、视频、音频</td>
>     </tr>
>
>     <tr>
>       <td>MiniMax-H3-Lite</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>图片、视频、音频</td>
>     </tr>
>   </tbody>
> </table>

### H3 系列扩展模型

<table>
  <thead>
    <tr>
      <th>模型</th>
      <th>输出分辨率</th>
      <th>输出视频\
      每秒</th>
      <th>输入视频\
      每秒</th>
      <th>输入图片\
      每张\
      超出免费额度后</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td rowSpan="2">**MiniMax-H3-Max**\
      支持图片、视频和音频参考，适合多素材视频创作</td>
      <td>768P</td>
      <td>¥0.50</td>
      <td>¥0.97</td>
      <td>¥0.50</td>
    </tr>

    <tr>
      <td>480P</td>
      <td>¥0.33</td>
      <td>¥0.37</td>
      <td>¥0.50</td>
    </tr>
  </tbody>
</table>

* **MiniMax-H3-Max**：每次任务前 **2 张**图片免费，超出部分按张计费；输入视频按时长及输出分辨率计费。音频输入免费。

> **查看扩展模型任务类型**
>
> <table>
>   <thead>
>     <tr>
>       <th>模型</th>
>       <th>文生 t2v</th>
>       <th>图生 i2v</th>
>       <th>首尾帧 fl2v</th>
>       <th>参考生 ref</th>
>     </tr>
>   </thead>
>
>   <tbody>
>     <tr>
>       <td>MiniMax-H3-Max</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>支持</td>
>       <td>图片、视频、音频</td>
>     </tr>
>   </tbody>
> </table>

### 视频再生成

将 MiniMax-H3 生成的 768P 视频再生成为 2K。

| **模型/接口** | **规格** | **输出视频** 每秒 | **输入视频** 每秒 | **输入图片** 每张 超出免费额度后 |
| :- | :- | -: | -: | -: |
| MiniMax-H3-Regeneration | 768P → 2K | ¥0.30 | ¥0.30 | ¥0.15 |

* 原任务的输入素材重新计费：图片前 **5 张**免费，超出部分按张计费；视频按原输入时长计费；音频免费。
* 再生成费用在原任务费用之外单独收取，包含再生成视频输出费及输入素材费。

### Context-IR

| **模型/接口** | **输入价格** 每百万 tokens | **输出价格** 每百万 tokens |
| :- | -: | -: |
| MiniMax-H3-Context-IR | ¥5.80 | ¥23.00 |

> **历史模型**
>
> | **模型** | **功能** | **单价**  元/视频 |
> | :- | :- | :- |
> | MiniMax-Hailuo-2.3-Fast | 图生视频，768P 6s | 1.35 |
> | MiniMax-Hailuo-2.3-Fast | 图生视频，768P 10s | 2.25 |
> | MiniMax-Hailuo-2.3-Fast | 图生视频，1080P 6s | 2.31 |
> | MiniMax-Hailuo-2.3 | 文生视频，图生视频，768P 6s | 2.00 |
> | MiniMax-Hailuo-2.3 | 文生视频，图生视频，768P 10s | 4.00 |
> | MiniMax-Hailuo-2.3 | 文生视频，图生视频，1080P 6s | 3.50 |
> | MiniMax-Hailuo-02 | 文生视频，图生视频，768P 6s | 2.00 |
> | MiniMax-Hailuo-02 | 文生视频，图生视频，768P 10s | 4.00 |
> | MiniMax-Hailuo-02 | 文生视频，图生视频，1080P 6s | 3.50 |
> | MiniMax-Hailuo-02 | 图生视频，512P 6s | 0.60 |
> | MiniMax-Hailuo-02 | 图生视频，512P 10s | 1.00 |

## 语音

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

**语音识别（ASR）**

| **计费项** | **接口** | **接口说明** | **单价** 元/小时 |
| :- | :- | :- | :-: |
| 语音识别 | Speech-to-Text | 音频转文本，支持流式返回、说话人分离与字幕（srt/vtt）导出。 | 2.50 |

**语音合成（TTS）**

| **计费项** | **模型** | **接口说明** | **单价** 元/万字符 |
| :- | :- | :- | :-: |
| 同步语音合成 T2A | speech-2.8-hd | 支持音量、语调、语速调整和混音，支持比特率、采样率相关参数调整，支持音频时长、音频大小等返回参数。适用于短文本快速合成，如闲聊、对话等场景。 | 3.50 |
| 同步语音合成 T2A | speech-2.8-turbo | 同上，速度更快、成本更低。 | 2.00 |
| 异步长文本语音合成 T2A Async | speech-2.8-hd | 支持文本到语音的异步生成，单次最大支持 100 万字符，生成结果支持异步检索。 | 3.50 |
| 异步长文本语音合成 T2A Async | speech-2.8-turbo | 同上，速度更快、成本更低。 | 2.00 |

> [!NOTE]
>
> 计费单位为字符数，以 10,000 个字符（输入）为单位。1 个汉字算 2 个字符；英文字母、希腊字母、标点符号、特殊符号、空格、回车等各算 1 个字符。

**音色管理**

| **计费项** | **接口说明** | **单价** 元/音色 | **计费说明** |
| :- | :- | :-: | :- |
| **音色设计** Voice Design | 基于用户输入的声音描述 prompt 生成音色（voice\_id），可用于同步/异步语音合成接口。 | 9.90 | 生成音色时不立即收费，首次使用该音色进行合成时才计入。接口内的试听语音合成按 2.00 元/万字符计费。 |
| **快速复刻** Voice Cloning | 基于大语言模型的音色克隆，无需超长时长的高质量原音频，即可在极短时间内完成音色复刻，并保持与原音色的高保真还原。 | 9.90 | 复刻音色时不立即收费，首次使用该音色进行合成时才计入。试听字符按所选试听模型的单价计费。 |

> **历史模型**
>
> | **计费项** | **模型** | **单价** 元/万字符 |
> | :- | :- | :-: |
> | 同步语音合成 T2A | speech-2.6-hd / speech-02-hd | 3.50 |
> | 同步语音合成 T2A | speech-2.6-turbo / speech-02-turbo | 2.00 |
> | 异步长文本语音合成 T2A Async | speech-2.6-hd / speech-02-hd | 3.50 |
> | 异步长文本语音合成 T2A Async | speech-2.6-turbo / speech-02-turbo | 2.00 |

## 图像

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

| **模型** | **接口说明** | **单价**  元/张 |
| :- | :- | :-: |
| image-01 image-01-live | 支持用户通过文本描述或参考图片生成图片 | 0.025 |

## 音乐

> [!NOTE]
>
> 自 2026 年 8 月 20 日起，付费接口（音乐生成、歌词生成）不再面向新用户提供服务，历史付费用户可继续使用现有 API 服务；免费音乐生成接口（Music-3.0-free、Music-2.6-free、music-cover-free）停止服务。
>
> 如需体验或使用音乐生成能力，可前往 [MiniMax Audio](https://www.minimax.cn/audio)，或使用已发布在 [Hugging Face](https://huggingface.co/MiniMaxAI/MiniMax-Music3) 和 [魔搭 ModelScope](https://modelscope.cn/models/MiniMax/MiniMax-Music3) 的 MiniMax Music 3 开源模型。

| **模型** | **接口说明** | **单价**  元/首 |
| :- | :- | :-: |
| Music-3.0（已下线） | RPM = 120，若需提升可联系销售定制 | 1.0 |
| Music-2.6（已下线） | RPM = 120，若需提升可联系销售定制 | 1.0 |
| 歌词生成（已下线） | 歌词生成/编辑 | 0.05 |

> **历史模型**
>
> | **模型** | **接口说明** | **单价**  元/首 |
> | :- | :- | :-: |
> | Music-2.5+（已下线） | 最新音乐生成模型，纯音乐解锁，突破风格边界 | 1.0 |
> | Music-2.5（已下线） | 全维度突破，指挥细节，定义真实 | 1.0 |
> | Music-2.0（已下线） | 多变音色，丰富乐器表现 | 0.25 |

## MCP

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

| **模型** | **接口说明** | **输入价格** 元/次 |
| :- | :- | :-: |
| API-vlm | 通过 **M Plan MCP** 插件或工具自带的视觉接口调用 | 0.025 |

通过 M Plan 调用 API-vlm 时，会按其按量计费价格扣减套餐内 M Plan 额度；套餐内额度耗尽且已购积分可用时，超出部分可由已购积分自动补充支付。

🔔 **定价调整预告**：自2026年7月22日起，API-vlm 按量价格调整为 ¥0.025 元/次。M Plan 套餐内单次 API-vlm 调用扣减的 token 额度将同步减少，同等套餐可支持更多次调用。接口与能力保持不变，无需任何代码调整。

## 服务端工具&#x20;

[立即充值](https://platform.minimax.cn/user-center/payment/balance)

| **服务端工具** | **接口说明** | **单价**  元/次 |
| :- | :- | :-: |
| **web\_search** | 联网搜索，模型在服务端自动执行搜索并基于结果作答，详见[服务端工具](https://platform.minimaxi.com/docs/guides/server-tools.md) | 0.03 |

## 语音资源包

## HD 系列

[立即购买](https://platform.minimax.cn/user-center/payment/subscription)

| **分类** | **语音套餐一** **（节省 10%）** | **语音套餐二** **（节省 15%）** | **语音套餐三** **（节省 20%）** | **商务定制** |
| :- | :- | :- | :- | :- |
| 折扣价 | ¥630 | ¥5,950 | ¥56,000 | 基于量级的额外折扣 |
| 原价 | ¥700 | ¥7,000 | ¥70,000 | —— |
| 有效期 | 1 个月 | 3 个月 | 1 年 | —— |
| 总字符数量 | 2,000,000 字符 | 20,000,000 字符 | 200,000,000 字符 | —— |
| 功能 | 支持 T2A v2 / T2A async v2 接口 RPM：60 支持 HD 系列模型 赠送 10 个快速克隆音色 | 支持 T2A v2 / T2A async v2 接口 RPM：200 支持 HD 系列模型 赠送 30 个快速克隆音色 | 支持 T2A v2 / T2A async v2 接口 RPM：500 支持 HD 系列模型 赠送 300 个快速克隆音色 | 无限 RPM/TPM 模型更新优先体验 专属的安全和稳定性保障 |

## Turbo 系列

[立即购买](https://platform.minimax.cn/user-center/payment/subscription)

| **分类** | **语音套餐一** **（节省 10%）** | **语音套餐二** **（节省 15%）** | **语音套餐三** **（节省 20%）** | **商务定制** |
| :- | :- | :- | :- | :- |
| 折扣价 | ¥360 | ¥3,400 | ¥32,000 | 基于量级的额外折扣 |
| 原价 | ¥400 | ¥4,000 | ¥40,000 | —— |
| 有效期 | 1 个月 | 3 个月 | 1 年 | —— |
| 总字符数量 | 2,000,000 字符 | 20,000,000 字符 | 200,000,000 字符 | —— |
| 功能 | 支持 T2A v2 / T2A async v2 接口 RPM：60 支持 Turbo 系列模型 赠送 10 个快速克隆音色 | 支持 T2A v2 / T2A async v2 接口 RPM：200 支持 Turbo 系列模型 赠送 30 个快速克隆音色 | 支持 T2A v2 / T2A async v2 接口 RPM：500 支持 Turbo 系列模型 赠送 300 个快速克隆音色 | 无限 RPM/TPM 模型更新优先体验 专属的安全和稳定性保障 |

## 视频资源包

[立即购买](https://platform.minimax.cn/user-center/payment/subscription)

视频资源包支持 Hailuo 系列视频模型，暂不支持 MiniMax H3

需要使用 H3？请点击 [按量购买 API](https://platform.minimax.cn/docs/pricing/overview#models/video)，或联系销售定制。

| **类型** | **视频基础包** **（节省 5%）** | **视频高级包** **（节省 10%）** | **视频进阶包** **（节省 15%）** | **视频企业包** **（节省 20%）** | **商务定制** |
| :- | :- | :- | :- | :- | :- |
| 折扣价 | ¥7,000 | ¥15,000 | ¥30,000 | ¥40,000 | —— |
| 原价 | ¥7,368 | ¥16,667 | ¥35,294 | ¥50,000 | |
| 有效期 | 1 个月 | 1 个月 | 1 个月 | 1 个月 | —— |
| 视频点数总量 | 3,680 | 8,330 | 17,650 | 25,000 | —— |
| 功能 | 支持 video generation 接口 RPM：20 | 支持 video generation 接口 RPM：30 | 支持 video generation 接口 RPM：40 | 支持 video generation 接口 RPM：50 | 无限 RPM/TPM 模型更新优先体验 专属的安全和稳定性保障 |

视频资源包相关事项如下：

1. 不同模型生成视频的扣减次数不同

* \[MiniMax-Hailuo-2.3-Fast]，生成单条768p，6s视频，扣减0.7视频点数
* \[MiniMax-Hailuo-2.3-Fast]，生成单条768p，10s视频，扣减1.1视频点数
* \[MiniMax-Hailuo-2.3-Fast]，生成单条1080p，6s视频，扣减1.3视频点数
* \[MiniMax-Hailuo-02]，生成单条512p，6s视频，扣减0.3视频点数
* \[MiniMax-Hailuo-02]，生成单条512p，10s视频，扣减0.5视频点数
* \[MiniMax-Hailuo-02] \[MiniMax-Hailuo-2.3]，生成单条768p，6s视频，扣减1视频点数
* \[MiniMax-Hailuo-02] \[MiniMax-Hailuo-2.3]，生成单条768p，10s视频，扣减2视频点数
* \[MiniMax-Hailuo-02] \[MiniMax-Hailuo-2.3]，生成单条1080p，6s视频，扣减2视频点数

2. 生成失败或命中安全审核的视频不会扣减视频点数
3. 资源包余量不继承，过期会自动清零

## 付费方式对比

MiniMax 开放平台支持按量计费和资源包。结合使用的模型、预计用量与使用周期，选择适合的付费方式。

### 按量计费与资源包

| 对比项 | 按量计费 | 资源包 |
| - | - | - |
| 适用场景 | 支持 MiniMax 全部模型与工具，按实际使用量计费，灵活满足多元化业务场景及各类调用需求 | 明确使用语音或视频模型，预计可在有效期内用完预购额度的业务场景。 |
| 付费方式 | 充值账户，按实际用量扣费 | 预付购买，在有效期内使用对应额度 |
| 支持范围 | MiniMax全系模型及工具 | 语音 HD / Turbo、Hailuo 系列视频 |
| 计费单位 | 按模型、规格与计费项确定 | 语音字符数、视频点数 |
| 开始使用 | [立即充值](https://platform.minimax.cn/user-center/payment/balance) | [立即购买](https://platform.minimax.cn/user-center/payment/subscription) |

### 选购资源包前

请核对适用模型、额度与有效期。语音 HD 与 Turbo 资源包分别适用于对应模型系列；视频资源包支持 Hailuo 系列，暂不支持 MiniMax H3。

[查看语音资源包](#packages/speech) · [查看视频资源包](#packages/video) · [查看使用规则](#guides/packages)

## 按量计费说明

按量计费使用开放平台普通 API Key，根据实际使用量消耗账户余额。以下价格均以人民币计价。

### 扣费与计量

* **扣费方式：**调用产生的费用从账户余额中扣除。
* **计量方式：**不同能力按 tokens、字符数、时长、图片张数、音色数量或调用次数计费，具体单位见对应价格表。
* **价格选择：**根据实际调用的模型、接口及规格匹配单价。例如，语言模型的输入长度与服务等级、视频的输出分辨率可能对应不同价格。

### 费用计算

> [!NOTE]
>
> \*\*费用计算：\*\*单项费用 = 实际用量 × 对应单价。计算前需统一用量与价格的单位；例如，按“元/百万 tokens”计价时，先将 token 用量除以 1,000,000，再乘以单价。一次调用涉及多个计费项时，总费用为各项费用之和。

具体单价见左侧模型价格与工具价格。语音、视频还可选购对应的资源包，详见[付费方式对比](#guides/compare)。

## 资源包使用规则

资源包通过预付购买额度，在有效期内用于适用的模型与接口。购买前请确认模型系列、使用量与有效期。

### 适用范围

| 对比项 | 语音资源包 | 视频资源包 |
| - | - | - |
| 适用模型 | HD 与 Turbo 系列分别对应各自资源包 | Hailuo 系列；暂不支持 MiniMax H3 |
| 适用接口 | 同步语音合成、异步长文本语音合成 | 视频生成 |
| 额度单位 | 字符数 | 视频点数 |
| 有效期 | 标准套餐按套餐分别为 1 个月、3 个月或 1 年 | 四档标准套餐均为 1 个月 |
| 到期规则 | 余量不继承，到期清零 | 余量不继承，到期清零 |
| 套餐详情 | [语音资源包](#packages/speech) | [视频资源包](#packages/video) |

### 额度计量与扣减

* **语音字符：**1 个汉字计 2 个字符；英文字母、希腊字母、标点、特殊符号、空格、回车等各计 1 个字符。
* **视频点数：**不同模型、分辨率与视频时长对应不同点数，点数不等同于视频条数。详见[视频点数扣减规则](#packages/video/package-rules)。
* **失败任务：**生成失败或命中安全审核的视频，不扣减视频点数。

### 有效期与使用限制

请结合有效期内的预估用量选择套餐。各套餐的调用频率限制与权益见对应套餐价格表。资源包优惠需结合实际使用模型、规格与额度利用情况比较，详见[付费方式对比](#guides/compare)。

## 常见问题

查看按量计费与资源包的常见问题。具体价格与套餐权益请以对应价格表为准。

### 计费与使用

> **M3 标准服务与优先服务有什么区别？**
>
> 优先服务让请求获得优先准入，按标准价格的 1.5 倍计费。调用时将 `service_tier` 设为 `priority` 即可启用。不同输入长度对应的价格档位见语言模型价格表。

> **视频价格包含输入素材费用吗？**
>
> H3 视频生成的输出与输入素材分别计费。输入图片超过免费张数后需额外付费，输入视频按时长及生成分辨率计费。视频再生成也需重新计算原任务使用的输入素材费用。

> **在哪里充值和查看账户费用？**
>
> 可在[账户充值页面](https://platform.minimax.cn/user-center/payment/balance)充值并查看余额，在[控制台](https://platform.minimax.cn/user-center/basic-information)查看用量与费用记录。平台支持余额预警，可在账户中设置。

> **资源包可以用于所有模型吗？**
>
> 资源包有明确的适用范围。语音包区分 HD 与 Turbo 系列；视频包支持 Hailuo 系列，暂不支持 H3。购买前请核对适用模型、额度和有效期，详见 [资源包使用规则](#guides/packages)。

> **资源包到期后，剩余额度可以保留吗？**
>
> 不可以。资源包余量不继承，到期清零。请结合预估用量和有效期选择合适的规格。
