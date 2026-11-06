# OnePlus 6 (enchilada) 内核云编译

在 GitHub Actions 上编译带 **SukiSU-Ultra (杂鱼) + SUSFS + KPM** 的 LineageOS 22.2 内核。
本机不装 WSL / Docker / Hyper-V / 任何编译器，虚拟化环境零占用。

## 产物

| 文件 | 用途 |
|---|---|
| `SukiSU-enchilada-<日期>-<run>.zip` | AnyKernel3 包，**Lineage Recovery 里直接刷** |
| `Image.gz` | 裸内核，需要自己打包 boot.img 时用 |

## 目录

```
.github/workflows/build-kernel.yml   # 编译流水线
tools/patch_ksu_hooks.py             # 给 4.9 内核插入 builtin 分支的 5 处 hook
tools/apply_config.py                # 把增量配置合并进 defconfig
tools/extra_config.conf              # 全功能 config（KSU/SUSFS/KPM/容器/网络/USB）
```

## 使用

1. 推到自己的 GitHub 仓库（public 无限额度，private 免费 2000 分钟/月）
2. Actions 页面点 `Build OnePlus6 Kernel` → `Run workflow`
3. 分支选 `builtin`（带 SUSFS + KPM）或 `main`（kprobes 方案）
4. 等 40~60 分钟，下载 artifact
5. 手机上：Lineage Recovery → Apply update → 刷 `SukiSU-enchilada-*.zip`

## 前置条件

- 手机已刷 **LineageOS 22.2**（Android 15），内核 4.9.337
- Bootloader 已解锁

## 编译失败常见原因

| 现象 | 原因 | 处理 |
|---|---|---|
| `defconfig 不存在` | 路径和预期不同 | 看日志里打印的 `arch/arm64/configs/` 列表，改 workflow 里的探测列表 |
| clang 拉取失败 | Lineage prebuilt 分支名变了 | workflow 已内置 googlesource 回退，两个都失败就换 `CLANG_VERSION` |
| `-Werror` 报错 | 4.9 老代码撞新 clang | 在 `Makefile` 里加 `KCFLAGS += -Wno-error`，或降 clang 版本 |
| `drivers/kernelsu` 为空 | setup.sh 网络抖动 | 重新跑一次 workflow |
| KSU 配置没生效 | defconfig 没合并成功 | 看 `out/.config` 里 `CONFIG_KSU` 是否 `=y` |

## 恢复

刷坏了用原版 LineageOS `boot.img` 救回：

```powershell
adb reboot bootloader
fastboot flash boot lineage-22.2-*-boot.img
fastboot reboot
```

## 注意

- 每次 LineageOS OTA 都会覆盖 boot，root 会掉，需要重刷本 workflow 的 zip
- `CONFIG_DEBUG_INFO` 故意没开（runner 只有 14GB 磁盘，开了必爆）；需要调 KPM 时再单独加
- 一加6 的 recovery 在 boot 分区里，AnyKernel3 会保留 ramdisk，正常不会丢 Recovery
