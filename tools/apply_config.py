#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 tools/extra_config.conf 的增量配置合并进内核 defconfig。

支持两种写法:
    CONFIG_X=y              → 启用
    # CONFIG_X is not set   → 显式禁用（Kconfig 里 default y 的选项必须这样关）

做两件事:
  1. 从 defconfig 里删掉同名的旧赋值（CONFIG_X=... 或 "# CONFIG_X is not set"）
  2. 追加新的配置行

用法:
    python3 tools/apply_config.py <defconfig_path> <extra_config_path>
"""

import re
import sys

RE_ENABLE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")
RE_DISABLE = re.compile(r"^#\s*(CONFIG_[A-Za-z0-9_]+) is not set$")


def parse_extra(path):
    """返回 [(key, kind, value)]，kind 为 'set' 或 'unset'"""
    wanted = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            m = RE_DISABLE.match(line)
            if m:
                wanted.append((m.group(1), "unset", None))
                continue
            if line.startswith("#"):
                continue
            m = RE_ENABLE.match(line)
            if m:
                wanted.append((m.group(1), "set", m.group(2)))
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

    with open(defconfig_path, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()

    keys = {k for k, _, _ in wanted}
    kept = []
    for line in lines:
        s = line.strip()
        if RE_ENABLE.match(s) and RE_ENABLE.match(s).group(1) in keys:
            continue
        if RE_DISABLE.match(s) and RE_DISABLE.match(s).group(1) in keys:
            continue
        kept.append(line)

    kept.append("")
    kept.append("# ===== 以下由 apply_config.py 追加 =====")
    enabled = 0
    disabled = 0
    for key, kind, value in wanted:
        if kind == "set":
            kept.append("%s=%s" % (key, value))
            enabled += 1
        else:
            kept.append("# %s is not set" % key)
            disabled += 1

    with open(defconfig_path, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")

    print("[+] 写入 %d 项到 %s（启用 %d，禁用 %d）"
          % (len(wanted), defconfig_path, enabled, disabled))
    for key, kind, value in wanted:
        if kind == "set":
            print("    %s=%s" % (key, value))
        else:
            print("    # %s is not set" % key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
