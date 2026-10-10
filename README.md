# 🐶 大狗叫

一个 **Windows 鼠标左键点击就播放音效** 的小工具（B 站梗：大狗叫叫叫）。
点一下鼠标左键，大狗就叫一声。基于 Windows 低级鼠标钩子 + MCI 播放引擎，
零第三方依赖、不弹窗、不卡鼠标。

---

## 功能特性

- **点击即响**：用 Windows 低级鼠标钩子（`WH_MOUSE_LL`）监听左键按下，每次点击立即触发一次播放
- **不卡鼠标**：钩子回调只做轻量投递，实际播放跑在独立线程，再快的手速也不会卡顿（内置 100ms 节流）
- **不弹窗**：用系统 MCI API（`winmm.mciSendStringW`）播放，不会像 PowerShell 那样弹黑框
- **深色琥珀主题**：贴合"大狗"氛围的无边框 GUI，自定义标题栏可拖动
- **可换音效**：支持 MP3 / WAV，内置默认狗叫，也可浏览选择自己的音频
- **无 Python 环境也能用**：已打包成单文件 exe，双击即用

---

## 文件说明

| 文件 / 目录 | 作用 |
|-------------|------|
| `dist/大狗叫.exe` | **最终产物**，单文件可执行程序，双击直接运行，无需 Python 环境 |
| `mouse_sound.py` | 核心源码。包含鼠标钩子、MCI 播放引擎、tkinter 无边框 GUI、配置读写 |
| `dog_bark.mp3` | 默认狗叫音效（从视频提取，42KB），会被打进 exe |
| `config.ini` | 运行时配置。记录你选择的音效路径（`[sound] audio_file`），exe 启动时自动读取 |
| `extract_audio.py` | 辅助脚本。从 MP4 视频提取音频为 MP3（需要 `av` 库），仅在你想自己生成音效时用 |
| `大狗叫.spec` / `大狗叫_debug.spec` | PyInstaller 打包配置，重新打包 exe 时用到 |
| `build/` | 打包中间产物，可安全删除 |
| `.venv/` | 本地 Python 虚拟环境（装了 PyInstaller），仅用于打包，普通用户不需要 |
| `dist/debug.log` | exe 运行时的日志（钩子安装/播放触发/退出记录） |

---

## 发给别人用：到底要下载哪些文件？

**不需要全部打包。** 取决于发给谁、想不想让对方也能改。

### 情况 A：发给"就想用"的人 → 只发 exe（推荐）

把 `dist\大狗叫.exe` 单独发出去就能用。它已**内置了狗叫音效**，
双击即用，无需 Python、无需安装任何东西。

- `config.ini` 不需要你提供：首次运行 exe 时会在 exe 旁边**自动生成**，用来记住音效路径，开箱即用
- 最干净的做法：把 `dist\大狗叫.exe` 压成 `大狗叫.zip` 发出去，对方解压双击即可

> 一句话：**只需要发 `大狗叫.exe` 这一个文件。**

### 情况 B：要发整个项目（含源码，方便对方改 / 重打包）

把整个目录发出去，但建议加 `.gitignore` 排除掉大体积的中间产物和虚拟环境：

```gitignore
# 打包中间产物
build/
__pycache__/

# 本地虚拟环境
.venv/

# 运行日志
dist/debug.log
```

这样对方拿到的就是：源码 + 默认音效 + spec + 现成 exe，
既可直接运行 exe，也可用 `.venv` 重新打包。

---

## 使用

### 方式一：直接用 exe（推荐）

1. 双击 `dist\大狗叫.exe`，弹出无边框小窗口
2. 点 **"🐕 开始叫"** —— 监听启动，之后每点一次鼠标左键就会叫一声
   - 按钮会变成 **"🔇 停止叫"**，点它可暂停监听
3. **试听**：在没开监听的情况下先听一下当前音效长什么样
4. 想换音效：在"音效文件"输入框点 **浏览** 选个 MP3 / WAV，再点"开始叫"
5. 关闭窗口：点右上角 **✕**、点 **退出** 按钮，或按 **Esc**

> exe 会自动在 `config.ini` 记住你选的音效路径，下次启动直接生效。

### 方式二：用 Python 源码跑

```powershell
# 需要 Python 3.x（用到 ctypes / tkinter / winsound，都是标准库）
python mouse_sound.py
```

也可以**后台无界面**运行（不弹窗口，常驻监听）：

```powershell
python mouse_sound.py --headless
```

按 `Ctrl+C` 退出。

---

## 换自己的音效（可选）

默认是内置狗叫。想用自己的声音文件：

- **最简单**：把音频（MP3/WAV）放到任意路径，在 GUI 里"浏览"选中即可，会自动写入 `config.ini`
- **从视频提取**：如果你有一段带狗叫的视频，用辅助脚本转成 MP3

```powershell
pip install av
python extract_audio.py <你的视频.mp4> dog_bark.mp3
```

然后把生成的 MP3 放进 GUI 选用，或直接覆盖 `dog_bark.mp3` 重新打包。

---

## 重新打包 exe（开发者）

```powershell
# 在项目 venv 里执行
.\.venv\Scripts\pyinstaller --onefile --windowed --name "大狗叫" `
  --clean --noconfirm --add-data "d:\bigdog\dog_bark.mp3;." d:\bigdog\mouse_sound.py
```

产物在 `dist\大狗叫.exe`。注意：
- 改完 `mouse_sound.py` 后必须重新打包，exe 才会同步更新
- 打包末尾可能有沙箱清理报错，**不影响** exe 生成，看到 `Build complete!` 即成功

---

## 技术要点

- **鼠标钩子**：`user32.SetWindowsHookExW(WH_MOUSE_LL=14, ...)`，回调里只投递到线程池，避免阻塞消息泵导致鼠标卡死
- **播放引擎演进**：`winsound`（<100KB 限制）→ WMP COM（不发声）→ PowerShell 兜底（弹窗）→ **MCI（最终，稳定无弹窗）**
- **兼容 PyInstaller**：用 `sys.frozen` / `sys._MEIPASS` 区分打包与源码运行；`--windowed` 模式下重定向 `stdout/stderr` 到 `debug.log`，避免 `print` 崩溃
- **无边框窗口**：`root.overrideredirect(True)` + 自绘标题栏（可拖动、可关闭）
