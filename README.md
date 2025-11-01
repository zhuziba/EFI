# OpenCore EFI 配置

本仓库提供适用于Intel i5-12490F处理器平台的OpenCore引导配置，支持安装和运行macOS系统。

## 硬件配置

| 组件 | 型号 | 备注 |
|------|------|------|
| 处理器 | Intel Core i5-12490F | 6核12线程 |
| 主板 | JGINYUE H610M-D PLUS WIFI | - |
| 显卡 | AMD Radeon RX 5700 | macOS原生支持 |
| 内存 | 请在使用前更新此处信息 | - |
| 存储 | 请在使用前更新此处信息 | - |
| 网卡 | Intel(R) Wireless-AC 9560 160MHz | - |
| 声卡 | 请在使用前更新此处信息 | - |

## 支持的系统版本
- macOS Ventura
- macOS Sonoma

## 使用说明
1. 确保你的硬件配置与本EFI兼容
2. 根据你的具体硬件，可能需要修改config.plist中的相关设置
3. 将EFI文件夹复制到你的ESP分区
4. 重启并选择OpenCore引导

## 已知问题
- 请在此处添加使用过程中遇到的问题和解决方案

## 注意事项
- 本配置仅供学习和测试使用
- 请确保在使用前更新SMBIOS信息，避免iCloud账号问题
- 定期更新OpenCore和驱动程序以获得最佳体验

## 感谢
- OpenCore团队
- 所有为此EFI提供帮助的开发者
