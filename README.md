# OpenCore EFI 说明文档

本仓库是一套基于 **OpenCore** 的黑苹果（Hackintosh）引导配置，适用于 **Intel i5-12490F** 平台，支持安装与运行 **macOS Sequoia**。

> 文档更新时间：2026-10-18（对应当前 `config.plist` 状态）

---

## 1. 硬件兼容性

| 组件 | 型号 | 驱动/处理方式 |
|------|------|----------------|
| 处理器 | Intel Core i5-12490F（12 代 Alder Lake，6 核 12 线程） | `SSDT-PLUG-ALT` + XCPM 电源管理 |
| 主板 | 精粤 JGINYUE H610M-D PLUS WIFI | CFG Lock 通过 `AppleXcpmCfgLock` 处理 |
| 显卡 | AMD Radeon RX 5700 | macOS 原生支持（`agdpmod=pikera`） |
| 无线网卡 | Intel Wireless-AC 9560 | `AirportItlwm`（需配合 OCLP 补丁，见下文） |
| 蓝牙 | Intel 板载蓝牙 | `IntelBluetoothFirmware` + `IntelBTPatcher` + `BlueToolFixup` |
| 有线网卡 | Realtek RTL8111 系列 | `RealtekRTL8111.kext` |
| 声卡 | 板载声卡（AppleALC `layout-id=11`） | `AppleALC.kext` |
| 内存 | *待补充* | — |
| 存储 | *待补充* | `NVMeFix` 提供 NVMe 电源管理优化 |

**支持的系统版本**：macOS Sequoia

---

## 2. 目录结构

```
EFI/
├── BOOT/
│   └── BOOTx64.efi              # OpenCore 引导入口（BIOS 实际加载的文件）
└── oc/
    ├── OpenCore.efi             # OpenCore 主程序
    ├── config.plist             # 主配置文件
    ├── config.backup-20261018.plist  # 2026-10-18 修改前备份（与 oldConfig.plist 内容相同）
    ├── oldConfig.plist          # 旧版配置（含调试参数的版本）
    ├── ACPI/                    # 6 个 SSDT 补丁
    ├── Drivers/                 # 4 个 UEFI 驱动
    ├── Kexts/                   # 16 个内核扩展
    ├── Resources/               # OpenCanopy 图形界面资源
    └── Tools/                   # （当前为空）
```

---

## 3. 组件详解

### 3.1 BOOT/

| 文件 | 说明 |
|------|------|
| `BOOTx64.efi` | OpenCore 的启动器副本，主板固件通过它进入 OpenCore 引导界面 |

### 3.2 oc/ACPI/（SSDT 补丁）

| 文件 | 用途 |
|------|------|
| `SSDT-EC.aml` | 屏蔽主板原生 EC（嵌入式控制器），提供假的 `EC` 设备，Hackintosh 必需 |
| `SSDT-PLUG-ALT.aml` | Alder Lake（12 代）专用的 XCPM 电源管理插件，使 CPU 变频/节能生效 |
| `SSDT-SBUS.aml` | 修复 SMBus 设备路径，供 `SMCProcessor` / `SMCSuperIO` 读取传感器 |
| `SSDT-RTCAWAC.aml` | 修复 RTC 与 AWAC 时钟冲突（现代主板必需，防止时间/唤醒异常） |
| `SSDT-USB-Reset.aml` | USB 设备复位修复 |
| `SSDT-USBX.aml` | 注入 USB 电源属性（睡眠供电/端口电流限制等，仅 Darwin 系统下生效） |

### 3.3 oc/Drivers/（UEFI 驱动）

| 驱动 | 用途 |
|------|------|
| `OpenRuntime.efi` | OpenCore 运行时基础驱动（**必需**，负责内存与 NVRAM 仿真） |
| `OpenCanopy.efi` | 图形化引导选择界面（配合 `Resources` 资源使用） |
| `HfsPlus.efi` | HFS+ 文件系统支持（读取 macOS 系统盘） |
| `ResetNvramEntry.efi` | 在引导界面提供"重置 NVRAM"菜单项 |

### 3.4 oc/Kexts/（内核扩展，共 16 个）

| Kext | 版本 | 作用 |
|------|------|------|
| `Lilu.kext` | 1.7.2 | 底层补丁框架，其他多数 kext 的依赖（必需） |
| `VirtualSMC.kext` | 1.3.8 | 模拟苹果 SMC 芯片（必需） |
| `SMCProcessor.kext` | 1.3.8 | CPU 温度/功耗传感器（配合 VirtualSMC） |
| `SMCSuperIO.kext` | 1.3.8 | 主板电压/风扇传感器（配合 VirtualSMC） |
| `WhateverGreen.kext` | 1.7.1 | 显卡综合补丁（本机用于 AMD Navi 显卡） |
| `AppleALC.kext` | 1.9.7 | 板载声卡驱动（`layout-id=11`） |
| `AirportItlwm.kext` | 2.4.0 | Intel 无线网卡驱动（AC 9560） |
| `IntelBluetoothFirmware.kext` | 2.5.0 | Intel 蓝牙固件加载 |
| `IntelBTPatcher.kext` | 2.5.0 | Intel 蓝牙控制器补丁 |
| `BlueToolFixup.kext` | 2.7.2 | 蓝牙工具链修复（macOS 12+，`MinKernel=21.0.0`） |
| `RealtekRTL8111.kext` | 3.0.4 | Realtek RTL8111 有线网卡驱动 |
| `NVMeFix.kext` | 1.1.4 | NVMe 固态硬盘电源管理优化（macOS 10.14+） |
| `RestrictEvents.kext` | 1.1.7 | 事件限制/系统信息修正（配合 `revpatch=sbvmm,cpuname` 显示真实 CPU 名称） |
| `USBToolBox.kext` | 1.2.0 | USB 定制框架 |
| `UTBDefault.kext` | 1.0 | USB 端口默认映射（与 USBToolBox 配套） |
| `XHCI-unsupported.kext` | 0.9.2 | 第三方主板的 XHCI 控制器支持 |

### 3.5 oc/Resources/

OpenCanopy 图形界面资源：主题图标（GoldenGate / Chardonnay / Syrah 三套）、启动标签、字体以及开机提示音 `OCEFIAudio_VoiceOver_Boot.wav`。

---

## 4. config.plist 关键配置

### 4.1 机型信息（PlatformInfo）

| 项目 | 值 |
|------|-----|
| 机型 | **MacPro7,1**（`Automatic=1`，`UpdateSMBIOSMode=Custom`） |
| 三码 | MLB / SystemSerialNumber / SystemUUID / ROM 已配置 |
| 特性 | `SpoofVendor=1`、`CustomSMBIOSGuid=1`（Kernel Quirk） |

> 注意：`config.backup-20261018.plist` 中的 MLB 为另一组值，说明三码近期被更新过。若更换机器或出现 iCloud 账号异常，请重新生成三码。

### 4.2 NVRAM 变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `boot-args` | `itlwm_he=1 agdpmod=pikera` | Intel WiFi HE 模式 + AMD Navi 显卡补丁（`agdpmod=pikera` 可消除 RX 5700 黑屏/花屏） |
| `csr-active-config` | `0x030a0000` | SIP 部分关闭（允许加载不受信任 kext，不影响日常使用） |
| `revcpu` / `revcpuname` | `1` / `12th Gen Intel(R) Core(TM) i5-12490F` | 通过 RestrictEvents 在"关于本机"显示真实 CPU 名称 |
| `revpatch` | `sbvmm,cpuname` | 同上 |

### 4.3 安全与引导（Misc）

- `SecureBootModel=Disabled`、`Vault=Optional`、`DmgLoading=Signed`
- `PickerMode=External`（OpenCanopy 图形界面）、`Timeout=3` 秒
- 无引导密码

### 4.4 重要 Quirks

**Kernel**
- `AppleXcpmCfgLock=1`：处理主板 CFG Lock（未在 BIOS 解锁 CFG Lock 也能正常启动）
- `DisableIoMapper=1`：关闭 VT-d 的 I/O 映射
- `ProvideCurrentCpuInfo=1`：12 代 CPU 必需
- `DisableLinkeditJettison=1`、`PanicNoKextDump=1`、`PowerTimeoutKernelPanic=1`

**Booter**
- `AvoidRuntimeDefrag=1`、`DevirtualiseMmio=1`、`RebuildAppleMemoryMap=1`、`SetupVirtualMap=1`、`ProvideCustomSlide=1`、`SyncRuntimePermissions=1`、`FixupAppleEfiImages=1`、`ProtectUefiServices=1`

**UEFI**
- `ReleaseUsbOwnership=1`、`RequestBootVarRouting=1`

**DeviceProperties**
- `PciRoot(0x0)/Pci(0x1f,0x3)` → `layout-id=11`（板载声卡）


---

## 6. 使用说明

1. **核对硬件**：确认你的机器与上表硬件一致（或按需调整 config.plist）。
2. **更新三码**（可选但推荐）：用 OCC / GenSMBIOS 重新生成 `MLB / Serial / UUID`，避免 iCloud/FaceTime 冲突。
3. **部署**：将整个 `EFI` 文件夹复制到 ESP（EFI 系统分区）。
4. **引导**：重启进入 BIOS，将启动项设置为 OpenCore（或 U 盘引导），开机进入 OpenCore 界面选择 macOS。

---

## 7. 注意事项与已知问题

- **无线网卡需打补丁**：Intel 无线网卡在 macOS 下需配合 OCLP 补丁才能稳定使用：
  https://github.com/JeoJay127/OCLP-X
- **升级前先备份**：更新 OpenCore 或 kext 前，先备份 `config.plist`（本仓库已保留 `config.backup-20261018.plist` 作为示例）。
- **升级 macOS 前确认兼容**：kext（尤其 `AirportItlwm`、`BlueToolFixup`、`NVMeFix`）需与目标系统版本匹配。
- **CFG Lock**：当前通过 `AppleXcpmCfgLock` 绕过；如主板 BIOS 支持，建议在 BIOS 中直接关闭 CFG Lock 后将该值改为 `0`。
- **内存/存储信息**：上表两项为占位，使用前请补充实际硬件型号。

---

## 8. 维护建议

- 保持 OpenCore、Lilu、VirtualSMC、AppleALC、WhateverGreen 等核心组件更新到最新稳定版。
- 每次修改 `config.plist` 前用 OCValidate（或 OpenCore 官方校验工具）检查语法。
- 出现引导问题优先开启 `debug=0x100 keepsyms=1` 查看详细日志定位。

---

## 致谢

- [OpenCore 官方文档](https://dortania.github.io/OpenCore-Install-Guide/)
- Acidanthera 团队（OpenCore 及全部核心 kext）
- 所有为黑苹果社区贡献的开发者

*本配置仅供学习与测试使用。*
