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
输出：`[Host]` 段模块（全量 `域名 = server:127.0.0.1`，DNS 层拦截，不依赖 MITM）。
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


# [Host] 全量黑洞（用户实测 2026-11-27 最终决策）：
#   `server:127.0.0.1` 统一用于全部域名（含曾有 AAAA（IPv6）记录的域名）——用户验证后决定不再拆 [Rule]。
#   注：早期 `X = 127.0.0.1` / `0.0.0.0` 纯 IP 写法实测不生效，必须 `server:` 前缀。
#   回退预案：若真机发现 server:127.0.0.1 拦不住 IPv6（有 AAAA 的域名从 IPv6 逃逸），
#   可把有 AAAA 的域名回退到 [Rule]（DOMAIN/DOMAIN-SUFFIX + REJECT）；需要时用
#   `dig @114.114.114.114 +short AAAA <域名>` 重新解析哪些域名有 AAAA（此前实测 342/1020 有）。
HOST_TARGET = "server:127.0.0.1"


def split_by_ip_version(all_domains):
    """全量统一进 [Host]（server:127.0.0.1）；[Rule] 段不再输出。

    回退预案：若真机验证发现 server:127.0.0.1 拦不住 IPv6，改回
    「有 AAAA → [Rule]，无 AAAA → [Host]」双段拆分即可（用 dig 重新解析生成清单）。
    """
    return set(all_domains), set()


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
    """产出全量 [Host] 段模块（含曾有 AAAA 的域名，统一 server:127.0.0.1）。

    参数保留 rule_domains/exact/suffix 以兼容「回退双段拆分」预案；当前 rule_domains 恒为空。
    """
    total = len(host_domains)
    v = version

    def host_line(d):
        line = f"{d} = {HOST_TARGET}"
        if d in annotations:
            line += f" # {annotations[d]}"
        return line

    lines = [
        "#!name=番茄小说 @zqzess",
        f"#!desc=番茄小说/红果 DNS 广告屏蔽, version = {v}",
        "#!desc=（[Host] DNS 层拦截，源自 home-dns-adblock/config）",
        "[Host]",
        "# [Host] DNS 层拦截：`域名 = server:127.0.0.1`，域名解析即指向本机回环、连接失败，不依赖 MITM。",
        "#   用户实测：早期纯 IP 写法（`X = 127.0.0.1` / `0.0.0.0` / `::`）不生效，须 `server:` 前缀。",
        "#   曾按 AAAA 拆 [Rule]（342 条有 IPv6），用户验证后决定全量统一 [Host]；",
        "#   若真机发现 IPv6 逃逸，可据 scripts/fanqie_aaaa_domains.txt 回退有 AAAA 域名到 [Rule]。",
        "# 白名单（正片/图床/基础设施）已剔除（来源 whitelist）；`-reading-ad.qznovelvod.com` 广告视频子域故意保留（正片走 -reading-video）。",
        "# ═══════════════════════════════════════════",
        "# 来源：home-dns-adblock/config（adblock-upstream.conf + adblock-extra.conf + adblock-fq.conf）",
        "# ═══════════════════════════════════════════",
        "# 上游广告规则（自动生成，勿手改）",
        "# 生成：GitHub Actions 定时任务（.github/workflows/sync-fanqie-module.yml）",
        f"# 条数：{total}（已过白名单过滤）",
    ]
    for d in sorted(host_domains):
        lines.append(host_line(d))
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
    module_rules = set(f"HOST,{d}" for d in host_domains) | set(
        f"{'DOMAIN' if d.count('.') >= 2 else 'DOMAIN-SUFFIX'},{d},REJECT" for d in rule_domains
    )
    qx_rules = set(f"DOMAIN,{d},REJECT" for d in exact) | set(
        f"DOMAIN-SUFFIX,{d},REJECT" for d in suffix
    )

    # 模块（全量 [Host] DNS 拦截）
    old_rules, annotations = read_existing(args.output)
    version = resolve_version(args.output, module_rules)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_module(host_domains, rule_domains, exact, suffix, version, annotations))
    print(
        f"模块：{len(host_domains)} 条 [Host] = {len(host_domains)} 条，version={version}"
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
