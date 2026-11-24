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
输出：`[Rule]` 段模块 ——
      域名标签数 > 2（完整主机名）→ `DOMAIN,X,REJECT`（精确拦）
      域名标签数 == 2（注册域）   → `DOMAIN-SUFFIX,X,REJECT`（拦 X 及全部子域）

版本规则：若生成的规则集与现有模块一致 → 版本号保持不变（幂等）；
         若有变化 → minor+1（遵循仓库「改动即 bump version」惯例）。
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


RULE_RE = re.compile(r"^(DOMAIN(?:-SUFFIX)?),([^,]+),REJECT\s*(?:#\s*(.*))?$")


def read_existing(path):
    """读取现有模块的规则集（剥行尾注释后比较）与每域名行尾注释（继承用）。"""
    rules, annotations = set(), {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for raw in f:
                m = RULE_RE.match(raw.strip())
                if m:
                    rules.add(f"{m.group(1)},{m.group(2)},REJECT")
                    if m.group(3):
                        annotations[m.group(2)] = m.group(3)
    return rules, annotations


def read_version(path):
    """读取现有模块的 version 字符串（如 "4.6" 或 "2026-11-24"）。"""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"version = (\S+)", line)
                if m:
                    return m.group(1)
    return None


def build_module(exact, suffix, version, annotations):
    total = len(exact) + len(suffix)
    v = version

    def rule(kind, d):
        line = f"{kind},{d},REJECT"
        if d in annotations:  # 继承现有模块的行尾手工注释
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
        lines.append(rule("DOMAIN", d))
    for d in suffix:
        lines.append(rule("DOMAIN-SUFFIX", d))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成 FanQieNovel.module")
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--extra", required=True)
    ap.add_argument("--fq", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    domains = set()
    for path in (args.upstream, args.extra, args.fq):
        try:
            domains |= parse_config(path)
        except FileNotFoundError:
            print(f"错误：找不到输入文件 {path}", file=sys.stderr)
            sys.exit(1)

    exact, suffix = classify(domains)
    new_rules = set(f"DOMAIN,{d},REJECT" for d in exact) | set(
        f"DOMAIN-SUFFIX,{d},REJECT" for d in suffix
    )

    cur = read_version(args.output)
    old_rules, annotations = read_existing(args.output)
    today = datetime.date.today().isoformat()
    if cur is not None and old_rules == new_rules:
        version = cur  # 规则集无变化 → 保持原版本日期（幂等）
    else:
        version = today  # 规则集有变化或首次生成 → 版本 = 规则最后变化日期

    content = build_module(exact, suffix, version, annotations)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    print(
        f"生成完成：{len(exact)} 精确 + {len(suffix)} 后缀 = {len(exact) + len(suffix)} 条，"
        f"version={version}"
    )


if __name__ == "__main__":
    main()
