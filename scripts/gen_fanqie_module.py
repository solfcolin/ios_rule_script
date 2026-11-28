#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 Shadowrocket/module/FanQieNovel.module（来自 home-dns-adblock 的 dnsmasq 配置）。

用法：
    python3 scripts/gen_fanqie_module.py \
        --upstream config/adblock-upstream.conf \
        --extra    config/adblock-extra.conf \
        --fq       config/adblock-fq.conf \
        --output   Shadowrocket/module/FanQieNovel.module

输入：三个 dnsmasq 风格配置文件（`address=/X/` 行，`#` 开头为注释）。
输出：`[Rule]` 段模块 —— 全量 DOMAIN / DOMAIN-SUFFIX + REJECT（DNS 层拦截，不依赖 MITM）。
      完整主机名 → `DOMAIN,X,REJECT`（精确拦）；注册域 → `DOMAIN-SUFFIX,X,REJECT`（拦 X 及全部子域）。
      若指定 --output-qx，另生成 Quantumult X 分流文件（与模块同源同规则集，同为 REJECT 形式）。

版本规则：版本 = 规则集最后变化日期；规则集无变化保持原日期（幂等），有变化置为今天。
"""
import argparse
import datetime
import os
import re
import sys


def parse_config(path):
    """提取配置里启用的 address=/X/ 条目（跳过 # 注释行）。"""
    domains = set()
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^address=/([^/]+)/", line)
            if m:
                domains.add(m.group(1))
    return domains


def classify(domains):
    """按标签数分成 精确(>2段) 与 后缀(2段) 两组，各自排序。"""
    exact, suffix = [], []
    for d in sorted(domains):
        if d.count(".") == 1:
            suffix.append(d)
        else:
            exact.append(d)
    return exact, suffix


# 全量 [Rule] REJECT（用户 2026-11-28 决策，改回 [Rule]）：
#   [Host] `server:127.0.0.1` 只拦 IPv4（A 记录），有 AAAA（IPv6）记录的域名会从 IPv6 逃逸
#   （2026-11-27 实测 342/1020 条有 AAAA），且丢响应级语义；[Rule] REJECT 无此问题。
#   历史实测坑（若再考虑 [Host]）：纯 IP 写法（`X = 127.0.0.1` / `0.0.0.0` / `::`）不生效，
#   必须 `server:` 前缀（见 commit 8312968）。


RULE_RE = re.compile(r"^(DOMAIN(?:-SUFFIX)?),([^,]+),REJECT\s*(?:#\s*(.*))?$")
HOST_RE = re.compile(r"^([^#=]+?)\s*=\s*server:127\.0\.0\.1\s*(?:#\s*(.*))?$")


def read_existing(path):
    """读取现有规则集（新 [Host] 行 + 旧 [Rule] REJECT 行兼容）与行尾注释。"""
    rules, annotations = set(), {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                m = RULE_RE.match(line)
                if m:
                    rules.add(f"{m.group(1)},{m.group(2)},REJECT")
                    if m.group(3):
                        annotations[m.group(2)] = m.group(3)
                    continue
                m = HOST_RE.match(line)
                if m:
                    domain = m.group(1).strip()
                    rules.add(f"HOST,{domain}")
                    if m.group(2):
                        annotations[domain] = m.group(2)
    return rules, annotations


def read_version(path):
    """读取现有文件的 version 字符串（如 "2026-11-24" 或 "4.6"）。"""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"(?:version = |生成时间：)(\d{4}-\d{2}-\d{2}|\d+(?:\.\d+)?)", line)
                if m:
                    return m.group(1)
    return None


def build_module(exact, suffix, version, annotations):
    """产出全量 [Rule] 段模块（DOMAIN 精确 / DOMAIN-SUFFIX 注册域 + REJECT）。"""
    total = len(exact) + len(suffix)
    v = version

    def rule_line(kind, d):
        line = f"{kind},{d},REJECT"
        if d in annotations:
            line += f" # {annotations[d]}"
        return line

    lines = [
        "#!name=番茄小说 @zqzess",
        f"#!desc=番茄小说/红果 DNS 广告屏蔽, version = {v}",
        "#!desc=（[Rule] DNS 层拦截，源自 home-dns-adblock/config）",
        "[Rule]",
        "# 全部走 [Rule] DNS 层拦截，不依赖 [Host] 映射、不依赖 MITM。",
        "#   完整广告主机名 → `DOMAIN,X,REJECT` 精确拦（如 ads3-normal-hl.zijieapi.com）。",
        "#   注册域 → `DOMAIN-SUFFIX,X,REJECT` 拦 X 及全部子域（如 googleadservices.com）。",
        "#   曾于 2026-11-27 全量改用 [Host] `server:127.0.0.1`，2026-11-28 改回 [Rule]：",
        "#   server:127.0.0.1 只拦 IPv4（A 记录），有 AAAA（IPv6）记录的域名会逃逸（实测 342/1020 条有）。",
        "# 白名单（正片/图床/基础设施）已剔除（来源 whitelist）；`-reading-ad.qznovelvod.com` 广告视频子域故意保留（正片走 -reading-video）。",
        "# ═══════════════════════════════════════════",
        "# 来源：home-dns-adblock/config（adblock-upstream.conf + adblock-extra.conf + adblock-fq.conf）",
        "# ═══════════════════════════════════════════",
        "# 上游广告规则（自动生成，勿手改）",
        "# 生成：GitHub Actions 定时任务（.github/workflows/sync-fanqie-module.yml）",
        f"# 条数：{total}（已过白名单过滤）",
        f"# 精确 {len(exact)} 条 + 后缀 {len(suffix)} 条",
    ]
    for d in exact:
        lines.append(rule_line("DOMAIN", d))
    for d in suffix:
        lines.append(rule_line("DOMAIN-SUFFIX", d))
    return "\n".join(lines) + "\n"


def build_qx_list(exact, suffix, version):
    """生成 Quantumult X 分流文件（filter_remote）：DOMAIN / DOMAIN-SUFFIX + REJECT。"""
    total = len(exact) + len(suffix)
    lines = [
        "# 番茄小说 @zqzess",
        f"# 生成时间：{version}（规则最后变化日；仅在规则集变化时重生成并更新）",
        "# 用法：Quantumult X「分流」-> 「引用规则」，作为 filter_remote 引入，REJECT 走 REJECT 策略组。",
        "#",
        "# 上游广告规则（自动生成，勿手改；与 Shadowrocket 模块同源同规则集，同为 DOMAIN/DOMAIN-SUFFIX + REJECT）",
        "# 生成：GitHub Actions 定时任务（.github/workflows/sync-fanqie-module.yml）",
        f"# 条数：{total}（{len(exact)} 精确 + {len(suffix)} 后缀）",
        "#",
        "# 注意：本文件全量按上游生成，未保留原手写 QX 特化规则（IP-CIDR / 精确 DOMAIN 绕开 QX DOMAIN-SUFFIX 等），",
        "#       若个别域在圈X DOMAIN-SUFFIX 下不命中，按真机请求记录改回精确 DOMAIN。",
    ]
    for d in exact:
        lines.append(f"DOMAIN,{d},REJECT")
    for d in suffix:
        lines.append(f"DOMAIN-SUFFIX,{d},REJECT")
    return "\n".join(lines) + "\n"


def resolve_version(path, new_rules):
    """版本 = 规则集最后变化日期：规则集无变化保持原日期（幂等），有变化置为今天。"""
    cur = read_version(path)
    old_rules, _ = read_existing(path)
    if cur is not None and old_rules == new_rules:
        return cur
    return datetime.date.today().isoformat()


def main():
    ap = argparse.ArgumentParser(description="生成 FanQieNovel.module / FanQieNovel.list")
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--extra", required=True)
    ap.add_argument("--fq", required=True)
    ap.add_argument("--output", required=True, help="Shadowrocket 模块输出路径")
    ap.add_argument("--output-qx", default=None, help="Quantumult X 分流文件输出路径（可选）")
    args = ap.parse_args()

    domains = set()
    for path in (args.upstream, args.extra, args.fq):
        try:
            domains |= parse_config(path)
        except FileNotFoundError:
            print(f"错误：找不到输入文件 {path}", file=sys.stderr)
            sys.exit(1)

    exact, suffix = classify(domains)
    module_rules = set(f"DOMAIN,{d},REJECT" for d in exact) | set(
        f"DOMAIN-SUFFIX,{d},REJECT" for d in suffix
    )

    # 模块（全量 [Rule] DNS 拦截）
    old_rules, annotations = read_existing(args.output)
    version = resolve_version(args.output, module_rules)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_module(exact, suffix, version, annotations))

    # QX 分流文件（可选，各自独立跟踪版本；与模块同源同规则集，规则形式一致）
    if args.output_qx:
        version_qx = resolve_version(args.output_qx, module_rules)
        with open(args.output_qx, "w", encoding="utf-8") as f:
            f.write(build_qx_list(exact, suffix, version_qx))
        print(
            f"QX 分流：{len(exact)} 精确 + {len(suffix)} 后缀 = {len(exact) + len(suffix)} 条，"
            f"version={version_qx}"
        )

    print(
        f"模块：{len(exact)} 精确 + {len(suffix)} 后缀 = {len(exact) + len(suffix)} 条 [Rule]，"
        f"version={version}"
    )


if __name__ == "__main__":
    main()
