# Ryzen 7 9700X / MAXSUN B650M OpenCore EFI

这是从一台已验收的双系统电脑提取的 OpenCore 配置。测试系统为 macOS Sequoia 15.8.3（24H241），OpenCore 版本为 1.0.8。

| 硬件 | 已验证状态 |
| --- | --- |
| AMD Ryzen 7 9700X / 铭瑄 MS-Terminator B650M | macOS 从 tigo SSD 的 EFI 独立启动 |
| AMD Radeon RX 570 8 GB | Metal 2、双屏、DisplayPort 音频。仓库名中的 RX5802048 未在本机实测 |
| Realtek RTL8125BG | 有线网络 |
| Realtek RTL8852BE（PCI `10EC:B852`） | Wi‑Fi |
| Realtek Bluetooth（USB `0BDA:B85B`） | 蓝牙开启和设备配对 |
| AMD XH00 | 9 个逻辑 USB 端口的本机映射，含板载蓝牙 |

GoldenGate 图形菜单可选择 macOS 或 Windows，倒计时 10 秒。两轮睡眠唤醒已通过。USB-C 需按实际接线补扫。主板 3.5 mm 模拟音频和隔空投送未验收。无线配置限定于 macOS 15 的 Darwin 24。

## 组装 EFI

仓库包含公开版配置、两份 ACPI 表、USB 映射和上游依赖清单。组装脚本会校验每个下载 ZIP 的 SHA-256，并把完整启动文件放到 `build/EFI`。

### 从上游下载驱动

在 Mac 上准备 Python 3 和 Xcode Command Line Tools。从 [RealtekBluetoothFirmware 1.0.2 固定源码](https://github.com/kodeaqua/RealtekBluetoothFirmware/tree/22e501a8a0a7aba8bb4e594bc6f40b1a67391af9) 编译蓝牙 kext。原机版本用 macOS 15.5 SDK 构建。

```sh
git clone https://github.com/kodeaqua/RealtekBluetoothFirmware.git
git -C RealtekBluetoothFirmware checkout 22e501a8a0a7aba8bb4e594bc6f40b1a67391af9
make -C RealtekBluetoothFirmware test
make -C RealtekBluetoothFirmware
python3 build_efi.py --bluetooth-kext RealtekBluetoothFirmware/build/RealtekBluetoothFirmware.kext
```

上游驱动由各项目维护。 [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8) · [OcBinaryData](https://github.com/acidanthera/OcBinaryData/tree/640e7e9240938f2529e725351e1e1150dc3569db) · [AMD Vanilla](https://github.com/AMD-OSX/AMD_Vanilla) · [Dortania ACPI 指南](https://dortania.github.io/Getting-Started-With-ACPI/) · [AirPort_RTW89](https://github.com/FranciumOS-org/AirPort_RTW89/releases/tag/v0.7.1-BETA) · [OCLP 无线组件](https://github.com/dortania/OpenCore-Legacy-Patcher/tree/d9604c36a432eaf243ea18659ff4d208187452d7/payloads/Kexts/Wifi) · [BlueToolFixup](https://github.com/acidanthera/BrcmPatchRAM/releases/tag/2.7.2)

### 从本地完整备份离线组装

```sh
python3 build_efi.py --from-backup /path/to/private-EFI.zip
```

## 部署前

在本地填写自己的 `PlatformInfo → Generic` 中的 `SystemSerialNumber`、`MLB`、`SystemUUID` 和 `ROM`。若有同为 `MacPro7,1` 的可用私有配置，可用 `--identity-plist /path/to/private-config.plist` 将这四项复制到本地生成结果。保持这些值为本机私有。

用 OpenCore 1.0.8 的 `ocvalidate` 检查生成的配置，也可以在组装时传入 `--ocvalidate /path/to/ocvalidate`。测试前先备份现有 EFI，并从主板的一次性启动菜单确认新配置可用。Windows 的原生启动项可留作回退。
