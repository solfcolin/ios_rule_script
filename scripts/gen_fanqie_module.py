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
输出：`[Host]` + `[Rule]` 双段模块（DNS 层拦截，不依赖 MITM）——
      无 AAAA 记录的域名 → `[Host]`（`域名 = server:127.0.0.1`，只拦 IPv4）
      有 AAAA 记录的域名 → `[Rule]`（`DOMAIN/DOMAIN-SUFFIX + REJECT`，完整拦 v4+v6）
      分流依据：scripts/fanqie_{noaaaa,aaaa}_domains.txt（用 114.114.114.114 全量解析生成，可刷新）。
      若指定 --output-qx，另生成 Quantumult X 分流文件（QX 无 `[Host]` 语法，仍用 DOMAIN / DOMAIN-SUFFIX + REJECT）。

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


# [Host] / [Rule] 双段拆分（用户实测 2026-11-27）：
#   `server:127.0.0.1` 只拦 IPv4（A 记录）；有 AAAA（IPv6）记录的广告域名会从 IPv6 逃逸。
#   故按解析结果分流：无 AAAA → [Host]（`域名 = server:127.0.0.1`），有 AAAA → [Rule]（`DOMAIN/DOMAIN-SUFFIX + REJECT`）。
#   清单由 scripts/fanqie_{aaaa,noaaaa}_domains.txt 提供（用 114.114.114.114 全量解析生成，可重新跑脚本刷新）。
#   用户实测：早期纯 IP 写法（`X = 127.0.0.1` / `0.0.0.0` / `::`）不生效，必须 `server:` 前缀。
HOST_TARGET = "server:127.0.0.1"
AAAA_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fanqie_aaaa_domains.txt")
NOAAAA_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fanqie_noaaaa_domains.txt")


def load_domain_list(path):
    """读取每行一个域名的清单文件。"""
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip()}


def split_by_ip_version(all_domains):
    """按有无 AAAA 记录拆分：有 AAAA → [Rule]（REJECT），无 AAAA → [Host]（server:127.0.0.1）。"""
    aaaa = load_domain_list(AAAA_LIST)
    noaaaa = load_domain_list(NOAAAA_LIST)
    # 交集为空校验：防清单漂移导致漏规则
    overlap = aaaa & noaaaa
    if overlap:
        raise ValueError(f"AAAA/无AAAA 清单有交集，请重新生成：{sorted(overlap)[:5]}")
    host_domains = {d for d in all_domains if d in noaaaa}
    rule_domains = {d for d in all_domains if d in aaaa}
    return host_domains, rule_domains


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


def build_module(host_domains, rule_domains, exact, suffix, version, annotations):
    """产出 [Host]（无 AAAA）+ [Rule]（有 AAAA）双段模块。"""
    total = len(host_domains) + len(rule_domains)
    v = version

    def kind_of(d):
        return "DOMAIN" if d.count(".") >= 2 else "DOMAIN-SUFFIX"

    def host_line(d):
        line = f"{d} = {HOST_TARGET}"
        if d in annotations:
            line += f" # {annotations[d]}"
        return line

    def rule_line(d):
        line = f"{kind_of(d)},{d},REJECT"
        if d in annotations:
            line += f" # {annotations[d]}"
        return line

    lines = [
        "#!name=番茄小说 @zqzess",
        f"#!desc=番茄小说/红果 DNS 广告屏蔽, version = {v}",
        "#!desc=（[Host] + [Rule] DNS 层拦截，源自 home-dns-adblock/config）",
        "[Host]",
        "# [Host] DNS 层拦截：`域名 = server:127.0.0.1`，域名解析即指向本机回环、连接失败，不依赖 MITM。",
        "#   仅拦 IPv4（A 记录）；有 AAAA（IPv6）记录的域名放 [Rule]（见下）。",
        "#   用户实测：早期纯 IP 写法（`X = 127.0.0.1` / `0.0.0.0` / `::`）不生效，须 `server:` 前缀。",
        "#   清单：scripts/fanqie_noaaaa_domains.txt（无 AAAA）。",
        "# 白名单（正片/图床/基础设施）已剔除（来源 whitelist）；`-reading-ad.qznovelvod.com` 广告视频子域故意保留（正片走 -reading-video）。",
        "# ═══════════════════════════════════════════",
        "# 来源：home-dns-adblock/config（adblock-upstream.conf + adblock-extra.conf + adblock-fq.conf）",
        "# ═══════════════════════════════════════════",
        "# 上游广告规则（自动生成，勿手改）",
        "# 生成：GitHub Actions 定时任务（.github/workflows/sync-fanqie-module.yml）",
        f"# 条数：{total}（已过白名单过滤）",
        f"# [Host] {len(host_domains)} 条（无 AAAA）+ [Rule] {len(rule_domains)} 条（有 AAAA）",
    ]
    for d in sorted(host_domains):
        lines.append(host_line(d))
    lines.append("")
    lines.extend([
        "[Rule]",
        "# [Rule] DNS 层拦截：`DOMAIN/DOMAIN-SUFFIX + REJECT`，针对有 AAAA（IPv6）记录的域名——",
        "#   `server:127.0.0.1` 只拦 IPv4，IPv6 会逃逸，故这些域名用 [Rule] 完整拦截（DNS 层，不依赖 MITM）。",
        f"#   清单：scripts/fanqie_aaaa_domains.txt（{len(rule_domains)} 条）。",
    ])
    for d in sorted(rule_domains):
        lines.append(rule_line(d))
    return "\n".join(lines) + "\n"


def build_qx_list(exact, suffix, version):
    """生成 Quantumult X 分流文件（filter_remote）：DOMAIN / DOMAIN-SUFFIX + REJECT。"""
    total = len(exact) + len(suffix)
    lines = [
        "# 番茄小说 @zqzess",
        f"# 生成时间：{version}（规则最后变化日；仅在规则集变化时重生成并更新）",
        "# 用法：Quantumult X「分流」-> 「引用规则」，作为 filter_remote 引入，REJECT 走 REJECT 策略组。",
        "#",
        "# 上游广告规则（自动生成，勿手改；与 Shadowrocket 模块同源同规则集，QX 无 [Host] 语法故用 REJECT）",
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
    all_domains = set(exact) | set(suffix)
    host_domains, rule_domains = split_by_ip_version(all_domains)
    # 清单覆盖校验：上游域名必须全部落在两清单之一（防清单漂移/上游新增域未解析）
    unlisted = all_domains - host_domains - rule_domains
    if unlisted:
        print(f"警告：{len(unlisted)} 个域名不在 AAAA 清单中，默认归 [Host]（可重新生成清单）：",
              file=sys.stderr)
        host_domains |= unlisted
    module_rules = set(f"HOST,{d}" for d in host_domains) | set(
        f"{'DOMAIN' if d.count('.') >= 2 else 'DOMAIN-SUFFIX'},{d},REJECT" for d in rule_domains
    )
    qx_rules = set(f"DOMAIN,{d},REJECT" for d in exact) | set(
        f"DOMAIN-SUFFIX,{d},REJECT" for d in suffix
    )

    # 模块（无 AAAA → [Host]，有 AAAA → [Rule]）
    old_rules, annotations = read_existing(args.output)
    version = resolve_version(args.output, module_rules)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_module(host_domains, rule_domains, exact, suffix, version, annotations))
    print(
        f"模块：{len(host_domains)} 条 [Host]（无 AAAA）+ {len(rule_domains)} 条 [Rule]（有 AAAA）"
        f" = {len(host_domains) + len(rule_domains)} 条，version={version}"
    )

    # QX 分流文件（可选，各自独立跟踪版本）
    if args.output_qx:
        version_qx = resolve_version(args.output_qx, qx_rules)
        with open(args.output_qx, "w", encoding="utf-8") as f:
            f.write(build_qx_list(exact, suffix, version_qx))
        print(
            f"QX 分流：{len(exact)} 精确 + {len(suffix)} 后缀 = {len(exact) + len(suffix)} 条，"
            f"version={version_qx}"
        )

    print(
        f"模块：{len(exact)} 精确 + {len(suffix)} 后缀 = {len(exact) + len(suffix)} 条，"
        f"version={version}"
    )


if __name__ == "__main__":
    main()
