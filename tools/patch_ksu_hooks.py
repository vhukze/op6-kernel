#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给 LineageOS msm-4.9 (OnePlus 6 / enchilada, 内核 4.9.337) 内核
做 SukiSU-Ultra builtin 分支的源码级适配。

两部分:
  A. 4.9 内核需要的 hook 插入（execve / faccessat / newfstatat / reboot / policy_rwlock）
  B. SukiSU 源码在 <5.10 内核上的兼容修补（无效 include 加版本保护）

用法:
    python3 tools/patch_ksu_hooks.py <kernel_src_dir>

幂等: 已处理过的位置会跳过，可以重复执行。
"""

import sys
import os

# ---------------------------------------------------------------- A. hook 插入
# anchor_func   : 用于定位函数起点的唯一文本
# anchor_before : 在该文本所在行之前插入 hook（必须在 anchor_func 之后第一次出现）
# snippet       : 要插入的代码块，自带缩进与结尾空行
RULES = [
    {
        "name": "execve (sucompat)",
        "file": "fs/exec.c",
        "anchor_func": "static int do_execveat_common(int fd, struct filename *filename",
        "anchor_before": "if (IS_ERR(filename))",
        "guard": "ksu_handle_execveat",
        "snippet": (
            "#ifdef CONFIG_KSU\n"
            "\textern int ksu_handle_execveat(int *, struct filename **, void *, void *, int *);\n"
            "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
            "#endif\n"
            "\n"
        ),
    },
    {
        "name": "faccessat (sucompat)",
        "file": "fs/open.c",
        "anchor_func": "SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)",
        "anchor_before": "if (mode & ~S_IRWXO)",
        "guard": "ksu_handle_faccessat",
        "snippet": (
            "#ifdef CONFIG_KSU\n"
            "\textern int ksu_handle_faccessat(int *, const char __user **, int *, int *);\n"
            "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
            "#endif\n"
            "\n"
        ),
    },
    {
        "name": "newfstatat (sucompat)",
        "file": "fs/stat.c",
        "anchor_func": "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
        "anchor_before": "error = vfs_fstatat(dfd, filename, &stat, flag);",
        "guard": "ksu_handle_stat",
        "snippet": (
            "#ifdef CONFIG_KSU\n"
            "\textern int ksu_handle_stat(int *, const char __user **, int *);\n"
            "\tksu_handle_stat(&dfd, &filename, &flag);\n"
            "#endif\n"
            "\n"
        ),
    },
    {
        "name": "sys_reboot (supercall)",
        "file": "kernel/reboot.c",
        "anchor_func": "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,",
        "anchor_before": "/* We only trust the superuser with rebooting the system. */",
        "guard": "ksu_handle_sys_reboot",
        "snippet": (
            "#if defined(CONFIG_KSU) && !defined(CONFIG_KSU_KPROBES_KSUD)\n"
            "\textern int ksu_handle_sys_reboot(int, int, unsigned int, void __user **);\n"
            "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
            "#endif\n"
            "\n"
        ),
    },
]

# ------------------------------------------------------- policy_rwlock 去 static
POLICY_FILE = "security/selinux/ss/services.c"
POLICY_FROM = "static DEFINE_RWLOCK(policy_rwlock);"
POLICY_TO = "DEFINE_RWLOCK(policy_rwlock);"

# ------------------------------------------ B. SukiSU 源码在 4.9 上的兼容修补
# drivers/kernelsu 是 symlink 到 KernelSU/kernel
SUKISU_FIXES = [
    {
        "name": "static_call.h (Linux 5.10+)",
        "file": "drivers/kernelsu/kernel_includes.h",
        "old": "#include <linux/static_call.h>",
        "new": ("#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n"
                "#include <linux/static_call.h>\n"
                "#endif"),
        "guard": "KERNEL_VERSION(5, 10, 0)\n#include <linux/static_call.h>",
    },
]


def read(path):
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def write(path, data):
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(data)


def patch_one(root, rule):
    path = os.path.join(root, rule["file"])
    if not os.path.exists(path):
        return "MISSING", "文件不存在: " + rule["file"]

    src = read(path)
    if rule["guard"] in src:
        return "SKIP", "已包含 " + rule["guard"][:40]

    fi = src.find(rule["anchor_func"])
    if fi < 0:
        return "FAIL", "找不到函数锚点: " + rule["anchor_func"][:60]
    if src.find(rule["anchor_func"], fi + 1) >= 0:
        return "FAIL", "函数锚点不唯一，需人工确认: " + rule["file"]

    bi = src.find(rule["anchor_before"], fi)
    if bi < 0:
        return "FAIL", "函数体内找不到插入锚点: " + rule["anchor_before"][:60]

    line_start = src.rfind("\n", 0, bi) + 1
    write(path, src[:line_start] + rule["snippet"] + src[line_start:])

    if rule["guard"] not in read(path):
        return "FAIL", "写入后校验失败: " + rule["file"]
    return "OK", "已插入 hook（偏移 %d）" % line_start


def patch_policy_rwlock(root):
    path = os.path.join(root, POLICY_FILE)
    if not os.path.exists(path):
        return "MISSING", "文件不存在: " + POLICY_FILE
    src = read(path)
    if POLICY_TO in src and POLICY_FROM not in src:
        return "SKIP", "policy_rwlock 已处理"
    if POLICY_FROM not in src:
        return "SKIP", "未找到 static policy_rwlock（内核可能已回移植，可忽略）"
    write(path, src.replace(POLICY_FROM, POLICY_TO, 1))
    if POLICY_FROM in read(path):
        return "FAIL", "写入后校验失败: " + POLICY_FILE
    return "OK", "policy_rwlock 已去掉 static"


def patch_sukisu_source(root, fix):
    path = os.path.join(root, fix["file"])
    if not os.path.exists(path):
        return "MISSING", "文件不存在: " + fix["file"]
    src = read(path)
    if fix["guard"] in src:
        return "SKIP", "已修补"
    if fix["old"] not in src:
        return "SKIP", "源码里没有这行，可能上游已修"
    write(path, src.replace(fix["old"], fix["new"], 1))
    if fix["guard"] not in read(path):
        return "FAIL", "写入后校验失败: " + fix["file"]
    return "OK", "已加版本保护"


def main():
    if len(sys.argv) != 2:
        print("用法: python3 tools/patch_ksu_hooks.py <kernel_src_dir>")
        return 2

    root = sys.argv[1]
    if not os.path.isdir(os.path.join(root, "fs")):
        print("[!] 目标目录不像内核源码: " + root)
        return 2

    print("内核源码: " + os.path.abspath(root))
    print("=" * 70)
    print("[A] 4.9 内核 hook 插入")
    print("-" * 70)

    failed = 0
    for rule in RULES:
        status, msg = patch_one(root, rule)
        print("  [%-7s] %-24s %s" % (status, rule["name"], msg))
        if status in ("FAIL", "MISSING"):
            failed += 1

    status, msg = patch_policy_rwlock(root)
    print("  [%-7s] %-24s %s" % (status, "policy_rwlock", msg))
    if status in ("FAIL", "MISSING"):
        failed += 1

    print("-" * 70)
    print("[B] SukiSU 源码兼容修补")
    print("-" * 70)
    for fix in SUKISU_FIXES:
        status, msg = patch_sukisu_source(root, fix)
        print("  [%-7s] %-24s %s" % (status, fix["name"], msg))
        if status in ("FAIL", "MISSING"):
            failed += 1

    print("=" * 70)
    if failed:
        print("[!] 有 %d 处失败，请按上面提示人工处理后再继续" % failed)
        return 1
    print("[+] 全部处理完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
