# 个人 Android 客户端

原生 Java Activity + WebView，共用服务器上的个人看板。Android 6.0+，包名 `com.noticehub.personal`，版本 `1.0.2-personal` / versionCode `10003`。首次连接需自行输入电脑地址及 token，支持 `noticehub-personal://connect` 链接。无预设个人服务器地址或 token。

## Windows 构建

准备 JDK 17、Android SDK Platform 35、Build Tools 35。用 PowerShell 运行：

```powershell
.\build.ps1 -JdkHome 'C:\Java\jdk-17' -BuildTools 'C:\Android\Sdk\build-tools\35.0.0' -AndroidJar 'C:\Android\Sdk\platforms\android-35\android.jar'
```

默认输出 `output/notice-hub-personal.apk`，并在 `output/` 生成本地签名。保留签名文件才能对自己发布的 APK 进行覆盖升级。正式发布可传入已有 `-KeyStore`、`-PasswordFile` 和 `-KeyAlias`；密码文件仅包含密码，不要提交这些文件。

APK 的签名只用于安装与升级识别；客户端配置存储在设备自身。服务端账号、QQ 数据处理、模型和日历都在电脑完成，手机需能连到服务器。

本客户端没有经过全部 Android 机型的实机验证。`android/` 目录保留的是原版客户端；个人版源码在本目录，链接 scheme 和配置界面不同。
