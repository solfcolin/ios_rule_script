# CLAUDE.md

## 输出语言

始终使用中文回复用户，包括所有解释、说明、计划与总结。代码、命令、域名、规则标识符、正则表达式及引用的原文可保留原始形式，不必翻译。

## 项目说明

本仓库是各平台（Shadowrocket / Quantumult X）的分流规则、复写规则与脚本集合，规则文件手写维护。
以下约束是修改 `Shadowrocket/module/*.module` 时的硬要求，来自实际踩坑而非猜测。

## 核心机制：路径规则依赖 MITM，否则静默失效

Shadowrocket 的 `[URL Rewrite]` 与 `URL-REGEX` **只有在该域名被 MITM 时才能命中**。HTTPS 流量若不在
`[MITM] hostname` 列表里，内核只能看到 SNI/域名，**看不到 URL 路径**——规则语法完全正确也永不生效，
且没有任何报错，表现就是"规则写了但广告还在"。

所以：

1. 加任何按路径区分的规则，必须同步把对应域名加入 `[MITM] hostname`，两件事不能只做一半。
2. 排查"规则不生效"，**先核对 `[MITM] hostname` 覆盖范围**，再怀疑规则本身写得对不对。
3. 反例：`FanQieNovel.module` 里 byteimg 的 `ad-app-package` / `web.business.image` 路径规则长期存在，
   但 `*.byteimg.com` 从未进过 `[MITM]`，于是这些规则一直没生效。后果是 3.15→3.18 只能靠**逐版本加整域
   REJECT** 去追广告节点，最后把 REJECT 加到了抖音/番茄/西瓜共用的 CDN 上，连带屏蔽了正常视频与封面。
   修掉 MITM 这一环，才能同时做到"拦广告"和"不拦正片"。

## 核心机制：DNS 层拦截的实现与 `[Host]` 段的处置

**DNS 层拦截的本质**：`[Rule]` 里 `DOMAIN-SUFFIX` / `DOMAIN-WILDCARD` / `DOMAIN` + `REJECT`（或 `REJECT-DROP`
等）就是在解析域名之后、建立 TCP 连接之前拒绝，**不依赖 MITM**，也不走 `[URL Rewrite]`。这是 Shadowrocket
最「底层」的拦截机制。

**`[Host]` 段（`域名 = server:127.0.0.1`）是 Surge 语法，非 Shadowrocket 模块官方段**——官方无公开仓库/文档
（`github.com/shadowrocket/Shadowrocket` 404）；类官方站 shadowrocket.vip 主页只讲规则与 URL Rewrite，不提
`[Host]`；真实模块集合（deezertidal 200+ 个模块、blackmatrix7）均**零使用** `[Host]`。**但 3.43 起用户决策
试引入，2026-11-27 起 FanQieNovel.module 全量改用此写法**：所有「纯 REJECT」域名（精确主机 + 注册域）
统一映射到 `server:127.0.0.1`，**不再保留 `[Rule]` 段**（用户原话：当时不知道 DNS 拦截写法才用 `[Rule]`，
现在知道了就全改）。
**实测坑：纯 IP 写法（`X = 127.0.0.1` / `X = 0.0.0.0` / `::`）不生效，必须 `server:` 前缀**——
FanQieNovel.module 曾因纯 IP 写法无效而整段迁回 `[Rule]`（见 commit 8312968）。
**真机验证本段是否生效**（请求记录里命中表现为「连接 127.0.0.1 失败」）；异常时整体回退到 `[Rule]` REJECT。

- `[Host]` 对注册域做「整域后缀匹配」（`domain.com` 匹配该域及全部子域），但**表达不了主机前缀通配**
  （`p?-novel.byteimg.com`、`p*.douyinpic.com`、`v5-se*-reading-video.qznovelvod.com`）——这类若出现，
  不得硬扩成 `*.byteimg.com`（会违反上面「共用 CDN 族禁止整域 REJECT」，连带屏蔽正常封面/头像/商品图），
  需按具体域名逐条列。
- `[Host]` 映射 `server:127.0.0.1` 只等价于「连接失败」，**丢失** `REJECT-DICT` / `REJECT-200` / `REJECT-ARRAY` 的
  响应级语义（部分 SDK 靠它们避免报错/重试循环），故这三类动作的域名**不可**用本写法。
- Quantumult X 无 `[Host]` 段语法，`QuantumultX/FanQieNovel.list` 仍用 `DOMAIN/DOMAIN-SUFFIX + REJECT`
  （同源同规则集，仅语法载体不同）。

## 规则编写原则

- **共用 CDN 族禁止整域 REJECT**：`*.byteimg.com`、`*.douyinpic.com`、`*.ecombdimg.com`、`*.pstatp.com`
  由抖音 / 西瓜 / 番茄多家共用，正常封面、头像、商品图与广告素材混在同一批节点上，域名层无法区分，
  只能靠 `[URL Rewrite]` 按广告路径（`ad-app-package`、`ad-pattern`、`web.business.image`、`?from=ad` 等）拒绝。
- **只对有广告专用命名的节点做整域 REJECT**：例如 `*-ad-sign.byteimg.com`、`*-novel*.byteimg.com`、
  `*-reading*.fqnovelpic.com`、`*-ad.qznovelvod.com`——命名即专用，误伤面为零。
- **禁止对字节公共接口域使用 `DOMAIN-KEYWORD`**：`zijieapi.com`、`snssdk.com` 里承载 mssdk 签名、verify、
  vcs、mon 日志、设备风控等公共接口，整族拒绝会打断抖音等 App 的 feed 与登录，而不只是广告。
  广告投放接口要按具体主机族列（如 `ads{3,5}-normal-{hl,lf,lq}.zijieapi.com`）。
- **`URL-REGEX` 必须是合法正则**：以量词开头的写法（如 `*-default.ixigua.com`）会被内核在编译阶段丢弃，
  又是一条静默失效的规则。需要保留意图时，写成注释并说明为什么"故意不启用"（启用会命中的范围有多大）。
- **每次改动 bump `#!desc` 里的 version**，提交信息带上版本号（仓库现有惯例：`更新…版本升级至 3.xx，…`）。

## 改动后的自检

1. 用 node 跑一遍新正则，分别喂「应命中的广告 URL」和「应放过的正常 URL」，确认没有 false positive：
   `node -e 'const R=/^…/; console.log(R.test("…"))'`
2. 确认新增的路径规则所需域名都在 `[MITM] hostname` 里。
3. MITM 图片/视频 CDN 有风险：个别节点若做了证书校验（pinning），拦截反而导致封面异常。
   真机上验证抖音 feed 与番茄开屏页；异常时从 `[MITM] hostname` 移除对应域名，路径规则本身不受影响。
4. 定位"哪个域名被误拦"用 Shadowrocket 的请求记录（命中规则可见），按精确 `DOMAIN` / 路径补规则，
   不要靠扩大域名族来兜底。
