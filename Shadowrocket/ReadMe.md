# Shadowrocket（小火箭）

Shadowrocket（中文名「小火箭」）是 iOS 上的代理客户端，支持规则分流、模块复写、URL Rewrite 与 MITM 解密。
本目录存放专用于 Shadowrocket 的规则模块，格式与 Quantumult X（圈X）不兼容，请勿混用。

## 模块
- [番茄小说广告屏蔽](https://raw.githubusercontent.com/solfcolin/ios_rule_script/master/Shadowrocket/module/FanQieNovel.module)

## 模块里的 MITM 会生效吗

会生效，但你在 App 的「设置 → 解密(MITM)」页面**看不到**模块贡献的域名 —— 那里只显示主配置的 hostname，
容易让人误以为模块的 MITM 没写进去。Shadowrocket 实际按**并集合并**：

```
全局「解密」总开关 →  主配置 [MITM] hostname  ⊕  每个已启用模块的 [MITM] hostname
```

模块的 `[MITM]` 要生效，三件事必须同时满足：
1. 模块在「模块」列表里已勾选启用；
2. 「设置 → 解密」总开关已打开；
3. 证书已安装并信任（通用 → 关于本机 → 证书信任设置）。

### 唯一要死记的点：`%APPEND%` 必须带

```
hostname = %APPEND% ...   # 追加，安全
hostname = ...            # 替换，会清空主配置和其他模块的 hostname！
```

去掉 `%APPEND%` 的那条会**替换整个列表**，把别处设置的 MITM 全部清空，
表现是「装了某模块后别的功能突然连不上」。本目录所有模块统一带 `%APPEND%`。

### 验证模块 MITM 是否真的吃上

MITM 生效的唯一标志是**路径型规则开始命中**。用日志对比：
- **域名型 REJECT**（如 `pglstatp-toutiao.com`）：SNI 阶段即可拦截，**不依赖 MITM**，一定生效；
- **路径型规则**（`URL-REGEX` / `URL Rewrite`，如 `byteimg.com/ad-app-package`）：必须先被 `[MITM] hostname`
  覆盖，内核才看得到路径。

日志里路径型规则那行显示了完整路径并命中 → MITM 生效；若只有域名型在拦、路径型一条不命中
→ 模块未启用 / 总开关未开 / 证书未信任，三者之一。