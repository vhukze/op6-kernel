#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 tools/extra_config.conf 的增量配置合并进内核 defconfig。

做两件事:
  1. 从 defconfig 里删掉同名的旧赋值（CONFIG_X=... 或 "# CONFIG_X is not set"）
  2. 追加新的 CONFIG_X=y

用法:
    python3 tools/apply_config.py <defconfig_path> <extra_config_path>
"""

import re
import sys


def parse_extra(path):
    wanted = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$", line)
            if m:
                wanted.append((m.group(1), m.group(2)))
    return wanted


def main():
    if len(sys.argv) != 3:
        print("用法: python3 tools/apply_config.py <defconfig> <extra_config.conf>")
        return 2

    defconfig_path, extra_path = sys.argv[1], sys.argv[2]
    wanted = parse_extra(extra_path)
    if not wanted:
        print("[!] 增量配置为空: " + extra_path)
        return 2

    with open(defconfig_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    keys = {k for k, _ in wanted}
    kept = []
    for line in lines:
        s = line.strip()
        hit = False
        m = re.match(r"^(CONFIG_[A-Za-z0-9_]+)=", s)
        if m and m.group(1) in keys:
            hit = True
        m2 = re.match(r"^# (CONFIG_[A-Za-z0-9_]+) is not set$", s)
        if m2 and m2.group(1) in keys:
            hit = True
        if not hit:
            kept.append(line)

    kept.append("")
    kept.append("# ===== 以下由 apply_config.py 追加：SukiSU + 全功能可玩性配置 =====")
    for k, v in wanted:
        kept.append("%s=%s" % (k, v))

    with open(defconfig_path, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")

    print("[+] 已写入 %d 项配置到 %s" % (len(wanted), defconfig_path))
    for k, v in wanted:
        print("    %s=%s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
