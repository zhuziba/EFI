# 黑苹果 EFI 配置与维护说明

更新日期：2026-11-22

## 1. 文档用途

本文记录当前 macOS Sequoia 黑苹果 EFI 的组成、已完成的调整、验证方法、备份与回滚流程，以及仍需观察的问题。

本文以当前已确认的配置和运行时状态为准。后续修改 EFI 后，应同步更新本文，避免文档与实际配置不一致。

## 2. 系统与硬件概况

| 项目 | 当前配置 |
| --- | --- |
| 操作系统 | macOS Sequoia 15.8.3（24H241） |
| 引导器 | OpenCore 1.0.8 |
| SMBIOS | MacPro7,1 |
| CPU | Intel Core i5-12490F |
| 显卡 | AMD Radeon RX 5700 8GB |
| 内存 | 16GB DDR4-3200 |
| 有线网卡 | Realtek RTL8111H |
| 无线网卡 | Intel AX 系列 |
| USB 接收器 | Logitech 2.4GHz USB Receiver |
| EFI 分区 | 当前识别为 `disk1s1`，挂载点通常为 `/Volumes/NO NAME` |

> 磁盘编号和挂载点可能随系统环境变化。操作前应先用 `diskutil list` 确认，不要直接假设始终是 `disk1s1`。

## 3. 当前功能状态

- 已使用 **ForbiddenItlwm 0.6.0** 替代 AirportItlwm。
- ForbiddenItlwm 与 **BTLEAdvFixup 0.9.3** 配套工作，用于 Intel Wi-Fi、蓝牙 LE 广播和 AirDrop/AWDL 支持。
- 已确认 ForbiddenItlwm 与 BTLEAdvFixup 正常加载。
- AWDL BuildCheck 已确认为 `forbidden-0.6.0-beta.2-sequoia`。
- 近期多次采样中，AWDL 信道稳定为 **149**；信道属于运行时状态，后续仍可能变化。
- AppleALC 已更新至 **1.9.8**，音频布局按 **11** 生效。
- 最终优化后的 `config.plist` 已通过 OpenCore 1.0.8 的 `ocvalidate` 检查，结果为 `No issues found`，退出码为 `0`。
- 打字时整个界面掉帧的问题尚未解决，详见第 10 节。

## 4. EFI 目录与当前组成

EFI 主配置：

```text
/Volumes/NO NAME/EFI/OC/config.plist
```

### 4.1 Kexts

当前共启用 15 个 Kext：

| Kext | 版本 | 用途 |
| --- | --- | --- |
| Lilu.kext | 1.7.2 | 基础补丁框架 |
| VirtualSMC.kext | 1.3.8 | SMC 模拟 |
| SMCProcessor.kext | 1.3.8 | 处理器传感器支持 |
| SMCSuperIO.kext | 1.3.8 | Super I/O 传感器支持 |
| WhateverGreen.kext | 1.7.1 | 显卡相关补丁 |
| AppleALC.kext | 1.9.8 | 板载音频支持 |
| RestrictEvents.kext | 1.1.7 | 系统事件与 CPU 名称等补丁 |
| NVMeFix.kext | 1.1.4 | NVMe 电源与兼容性补丁 |
| RealtekRTL8111.kext | 3.0.4 | RTL8111H 有线网络 |
| USBToolBox.kext | 1.2.0 | USB 映射工具支持 |
| UTBDefault.kext | 未单独记录 | 当前使用的通用 USB 映射 |
| IntelBluetoothFirmware.kext | 2.5.0 | Intel 蓝牙固件加载 |
| BlueToolFixup.kext | 2.7.2 | macOS 蓝牙兼容性修复 |
| BTLEAdvFixup.kext | 0.9.3 | 蓝牙 LE 广播与 AWDL 配套修复 |
| ForbiddenItlwm.kext | 0.6.0 | Intel Wi-Fi 与 AWDL 支持 |

已移除的驱动：

- `IntelBTPatcher.kext`：避免与 BTLEAdvFixup 重复 hook。
- `XHCI-unsupported.kext`：本机仅确认 Intel `0x7ae0` XHCI 控制器，无需该驱动。

### 4.2 ACPI

当前 ACPI 文件：

```text
SSDT-SBUS.aml
SSDT-EC.aml
SSDT-PLUG-ALT.aml
SSDT-RTCAWAC.aml
SSDT-USB-Reset.aml
SSDT-USBX.aml
```

### 4.3 UEFI Drivers

当前驱动：

```text
HfsPlus.efi
OpenCanopy.efi
OpenRuntime.efi
ResetNvramEntry.efi
```

## 5. 无线、蓝牙与 AWDL 配置

### 5.1 驱动配套要求

ForbiddenItlwm 与 BTLEAdvFixup 必须作为一组维护。当前配套版本为：

```text
ForbiddenItlwm 0.6.0
BTLEAdvFixup 0.9.3
```

升级其中一个前，应先确认另一个是否需要同步升级。不要只替换驱动文件而遗漏 `config.plist` 中对应的 `Kernel/Add` 条目。

### 5.2 必须保留的 boot-args

当前完整参数：

```text
agdpmod=pikera -btleadv -itlawdlcoexprobe -itlawdliface -itlawdlnativeup -itlawdlcoexrx -itlawdlcoextx -itlawdlcoexmulti -itlawdlcoexdata -itlawdlmitx -itlawdlelicit -itlawdlcaps -itlawdlsvcmerge -itlawdlawsync itlawdlintcoal=4 -itlawdlcoexbatx -itlawdlcoexpeerpause -itlawdlcoexbatrace itlawdltxqueue=4096
```

注意事项：

- `agdpmod=pikera` 用于当前显卡配置，不应随意删除。
- `-btleadv` 和所有 `-itlawdl*` 参数是当前蓝牙 LE 广播、AWDL 和共存策略的一部分。
- 除非有明确的新版本说明或排错依据，否则不要精简、拆分或只保留部分 AWDL 参数。
- 修改后应完整复制，注意每个参数之间的空格，避免遗漏无连字符的 `itlawdlintcoal=4` 和 `itlawdltxqueue=4096`。

### 5.3 网络状态判断

使用 itlwm 系驱动时，以下命令可能显示未关联，即使实际网络正常：

```bash
networksetup -getairportnetwork en0
```

因此，不能只凭该命令判断 Wi-Fi 已断开。应结合 IP 地址、路由和实际联网情况检查：

```bash
ifconfig en0
ifconfig awdl0
ping -c 4 192.168.1.1
```

> 示例中的网关地址 `192.168.1.1` 应替换为本机实际路由器地址。

## 6. 重要 OpenCore 设置

| 配置项 | 当前值或状态 | 维护说明 |
| --- | --- | --- |
| `PlatformInfo.UpdateSMBIOSMode` | `Create` | 保持当前 SMBIOS 注入方式 |
| `PlatformInfo.CustomSMBIOSGuid` | `false` | 当前未启用自定义固件 GUID 注入 |
| `ROM` | `00:E0:22:1D:01:91` | 使用以太网真实 MAC，不使用 Wi-Fi 私密或轮换 MAC |
| `NVRAM csr-active-config` | `0x0A03` | SIP 保持当前设定，不为一般排错随意更改 |
| `Misc.Debug.Target` | `0` | 默认不生成启动调试日志 |
| `Misc.Debug.ApplePanic` | `false` | 当前关闭额外 panic 日志保存 |
| `Misc.Debug.LogModules` | 空 | 不额外筛选日志模块 |
| `Misc.Boot.LauncherOption` | `Full` | 保持完整启动项注册 |
| `UEFI.ProtocolOverrides.FirmwareVolume` | `false` | 当前关闭该协议覆盖 |
| `UEFI.Audio.AudioSupport` | `false` | 启动音频支持当前关闭 |
| `UEFI.Audio.PlayChime` | `Auto` | 由于 AudioSupport 关闭，不表示启动铃声明已启用 |
| `Kernel.Quirks.DisableIoMapper` | `true` | BIOS 状态未重新确认前不要直接改动 |
| `Kernel.Quirks.AppleXcpmCfgLock` | `true` | BIOS CFG Lock 状态未重新确认前不要直接改动 |
| `ResetSystem.efi` 工具条目 | 禁用 | 防止误用该工具 |
| 音频设备 `layout-id` | `11` | 保持为 11，不要因运行时显示 7 而改配置 |

音频设备路径：

```text
PciRoot(0x0)/Pci(0x1f,0x3)
```

### 6.1 RestrictEvents 当前并非空跑

NVRAM 中保留了以下配置：

```text
revpatch=sbvmm,cpuname
revcpu=1
revcpuname=12th Gen Intel(R) Core(TM) i5-12490F
```

这些参数用于当前系统补丁和 CPU 名称显示，不应在清理“冗余参数”时删除。

### 6.2 layout-id 为 7 是正常行为

当前 OpenCore 注入：

```text
layout-id = 11
```

AppleALC/Lilu 的处理过程为：

1. AppleALC 将原始 `layout-id=11` 复制为 `alc-layout-id=11`。
2. Lilu/AppleALC 再将普通 `layout-id` 改为兼容值 `7`。
3. AppleALC 控制器选择读取的是 `alc-layout-id`，因此实际音频布局仍为 **11**。

所以，IORegistry 中普通 `layout-id=7` 不代表注入失败，也不应据此把配置改成 7。

### 6.3 SMBIOS UUID 与 ROM 验证边界

- `UpdateSMBIOSMode=Create` 后，设备树中的 `system-id` 可以来自 `config.plist`，但系统报告的 Hardware UUID 仍可能来自固件。
- 两者不同不能单独证明 SMBIOS 注入失败，也不能宣称固件 UUID 已被覆盖。
- 修改 ROM 后，macOS IORegistry 不一定暴露可直接核对的 `ROM` 属性。
- 配置已写入且系统正常启动，不等于已经证明 iServices 一定接受该值；iServices 状态需另行验证。

## 7. 日常验证方法

### 7.1 挂载与卸载 EFI

先确认分区：

```bash
diskutil list
```

确认 EFI 确为 `disk1s1` 后挂载：

```bash
sudo diskutil mount disk1s1
```

操作完成后卸载：

```bash
sudo diskutil unmount "/Volumes/NO NAME"
```

系统会提示输入本机管理员密码。密码不应写进脚本、文档或配置备份说明中。

### 7.2 检查 plist 格式

```bash
plutil -lint "/Volumes/NO NAME/EFI/OC/config.plist"
```

该命令只验证 plist 格式，不能验证 OpenCore 配置语义。

### 7.3 检查 OpenCore 语义

使用与引导器匹配的 **OpenCore 1.0.8** `ocvalidate`：

```bash
"<ocvalidate路径>" "/Volumes/NO NAME/EFI/OC/config.plist"
```

理想结果：

```text
No issues found
```

`plutil` 与 `ocvalidate` 不能互相替代。重要修改后应两项都检查。

### 7.4 检查运行时驱动

```bash
kmutil showloaded | grep -Ei 'forbidden|btleadv|intelbluetooth|bluetool|applealc|restrictevents'
```

查看 AWDL、驱动标识及相关设备树信息：

```bash
ioreg -l | grep -Ei 'forbidden|btleadv|awdl|buildcheck'
```

查看系统网络与蓝牙信息：

```bash
system_profiler SPNetworkDataType SPBluetoothDataType SPAirPortDataType
```

> 第三方 Intel Wi-Fi 驱动下，`system_profiler` 或 `networksetup` 的 Airport 信息可能不完整，应结合 `ioreg`、`ifconfig` 和实际联网结果判断。

### 7.5 检查 SIP

```bash
csrutil status
```

如结果与当前 EFI 设定有关，修改前先确认是否确有必要。当前决定是保持 `0x0A03`，不是继续放宽 SIP。

## 8. 驱动与 OpenCore 更新流程

1. **先备份当前可启动的整份 `EFI/OC`**，不要只备份 `config.plist`。
2. 确认新版本支持 macOS Sequoia 和当前 OpenCore 版本。
3. 每次只更新一组驱动，避免同时更新多个组件后无法定位问题。
4. ForbiddenItlwm 与 BTLEAdvFixup 按配套版本一起评估。
5. 检查 Kext 文件名、版本和 `Kernel/Add` 条目是否一致。
6. 运行 `plutil -lint` 和匹配版本的 `ocvalidate`。
7. 重启后验证 Wi-Fi、蓝牙、AirDrop/AWDL、有线网络、音频和睡眠唤醒。
8. 确认稳定后再清理临时安装包；旧版本至少保留一个已验证可用的回滚副本。

不要为了让版本号更新而盲目升级。当前已验证稳定的组合优先于未经验证的新版本。

## 9. 备份与回滚

### 9.1 本地归档位置

EFI 归档：

```text
/Users/peng/Documents/Trae-CN/temp_20261115_01/EFI-archive-20261115/
```

主要内容包括：

- `OC-backup-20261115`：整份旧 OpenCore 目录。
- `config.backup-before-forbiddenitlwm.plist`：安装 ForbiddenItlwm 前的配置。
- `config.backup-20261115-pre-smbiosfix.plist`：SMBIOS 调整前配置。
- `config.backup-20261118-prelogfix.plist`：日志设置调整前配置。
- `config.backup-20261118-prelogmod.plist`：日志模块调整前配置。
- `config.backup-20261118-prerom.plist`：ROM 修改前配置。
- `config.backup-20261118-pretarget0.plist`：`Target=0` 修改前配置。
- `config.backup-20261119-preopt.plist`：最近一轮优化前配置。
- `oldConfig.plist`、`config.backup-20261018.plist`、`config.backup-20261022-aspm.plist`：更早配置。
- `AppleALC-1.9.7.kext`、`ForbiddenItlwm-0.5.4.kext`、`BTLEAdvFixup-0.9.1.kext`：旧驱动备份。

OpenCore 历史日志归档：

```text
/Users/peng/Documents/Trae-CN/temp_20261115_01/opencore-logs-20261118/
```

目前归档了 15 个历史日志。`Target=0` 后，正常情况下不会继续每次启动生成日志。

建议另外把最近一份可启动的整份 EFI 备份到外置磁盘或启动 U 盘。仅保存在本机磁盘上的备份，在磁盘或系统损坏时可能无法使用。

### 9.2 修改前新增备份

挂载 EFI 后，可创建带时间戳的整份 OC 备份：

```bash
BACKUP_DIR="$HOME/Documents/Trae-CN/temp_20261115_01/EFI-archive-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -R "/Volumes/NO NAME/EFI/OC" "$BACKUP_DIR/OC"
```

备份完成后，再开始修改。

### 9.3 配置级回滚

适用于只修改了 `config.plist`，且当前系统仍能启动的情况：

1. 挂载 EFI。
2. 先保存当前故障配置，便于后续比较。
3. 选择对应修改时间之前的已知正常配置。
4. 将其恢复为 `EFI/OC/config.plist`。
5. 运行 `plutil -lint` 和 `ocvalidate`。
6. 卸载 EFI 并重启验证。

### 9.4 驱动或整份 OC 回滚

适用于驱动更新后无法联网、无法启动或出现内核问题的情况：

1. 优先使用提前准备的 OpenCore 启动 U 盘，或通过另一台电脑访问 EFI 分区。
2. 保留故障目录副本，不要直接清空 EFI。
3. 恢复与该配置匹配的 Kexts、ACPI、Drivers 和 `config.plist`。
4. 如进行整份回滚，尽量整组恢复，避免新配置与旧驱动混用。
5. 重启后逐项验证，不立即删除最后一份正常备份。

> 只恢复旧 `config.plist`、却保留不配套的新驱动，可能引入新的问题。配置级回滚与驱动级回滚应区分处理。

## 10. 已知行为与待观察事项

### 10.1 USB 定制映射暂缓

当前继续使用：

```text
USBToolBox.kext + UTBDefault.kext
```

用户已决定暂不制作真实 `UTBMap.kext`。后续如制作，应先备份，并重点验证：

- USB 2.0 与 USB 3.x 端口识别。
- 内置蓝牙端口类型。
- Logitech 接收器。
- 睡眠与唤醒后的 USB 状态。
- 外接设备热插拔。

本次不擅自添加或替换 USB 映射。

### 10.2 打字时整个界面掉帧

该问题 **尚未解决**。目前只完成运行时排查，未为这个问题修改 EFI。

已确认的情况：

- 内存空闲约 81%，没有明显内存压力。
- 未发现温控降频，`CPU_Speed_Limit=100`。
- RX 5700 的 Metal 3 正常，采样时 GPU 利用率约 3%、核心约 146MHz、温度约 55°C。
- WindowServer 约占用 32% CPU，Trae Renderer/GPU Helper 有明显占用。
- 显示器为 2560×1440、180Hz、30-bit、DisplayPort、原生无缩放。
- 初步怀疑方向是 180Hz 下的 CPU 侧合成或应用渲染，但尚不能据此确认根因，也没有证据表明显卡性能不足。

建议按以下顺序做对照测试：

1. 将显示器从 180Hz 临时改为 **60Hz**，测试相同打字操作。
2. 退出 GitHub Desktop 等暂时不用的 Electron 应用，减少干扰。
3. 分别测试普通文本编辑器与 Trae，确认是否只在特定应用中出现。
4. 如果 60Hz 下流畅，再依次测试 120Hz 或 144Hz。
5. 如果仍卡顿，再测试 macOS“降低透明度”选项。

在获得对照结果前，继续优先排查系统和应用层，不通过修改 EFI 盲目处理。

### 10.3 ESP 自动生成的目录

以下目录可能由系统自动重建：

```text
.fseventsd
.Trashes
System Volume Information
```

删除它们不属于永久优化，也不应反复清理来追求“绝对干净”。

### 10.4 BIOS 相关设置

当前保留：

```text
DisableIoMapper=true
AppleXcpmCfgLock=true
```

尚未重新确认 BIOS 中 VT-d 与 CFG Lock 的实际状态。未确认前，不建议直接关闭这两个 Quirk。

### 10.5 调试日志

当前为了日常使用已设置：

```text
Misc.Debug.Target=0
```

如后续出现启动故障，可临时恢复日志采集；问题定位完成后应归档日志并恢复日常设置，避免长期积累日志文件。

## 11. 推荐的维护检查清单

每次修改 EFI 前：

- [ ] 确认当前系统可以正常启动。
- [ ] 确认 EFI 分区与挂载点。
- [ ] 备份整份 `EFI/OC`。
- [ ] 记录本次只准备修改哪些项目。

修改后、重启前：

- [ ] 检查 Kext、ACPI、Driver 文件与 `config.plist` 条目一致。
- [ ] 检查 ForbiddenItlwm 与 BTLEAdvFixup 版本配套。
- [ ] 检查完整 boot-args 未被截断。
- [ ] 运行 `plutil -lint`。
- [ ] 使用 OpenCore 1.0.8 的 `ocvalidate`。
- [ ] 确认至少保留一份可回滚配置。

重启后：

- [ ] Wi-Fi 能连接并取得有效 IP。
- [ ] 蓝牙与蓝牙 LE 广播正常。
- [ ] AirDrop/AWDL 正常，必要时观察信道。
- [ ] 有线网络正常。
- [ ] 音频输出正常，且未误改 `layout-id=11`。
- [ ] 睡眠、唤醒及 USB 外设正常。
- [ ] 确认没有新增内核 panic 或异常启动日志。

## 12. 当前维护结论

当前 EFI 已完成 ForbiddenItlwm 安装、配套驱动更新、冗余驱动清理、日志收敛、ROM 调整及 OpenCore 语义检查。无线与 AWDL 相关组件按 ForbiddenItlwm 0.6.0、BTLEAdvFixup 0.9.3 和完整 AWDL boot-args 配套维护。

现阶段不建议为了“进一步优化”随意修改已验证正常的驱动组合。后续重点是保留可靠回滚副本、按需制作 UTBMap，以及完成打字掉帧的 60Hz/应用对照测试。
