# 📚 Windows命令完整速查表（Ollama + GPU + WSL）

## 一、Ollama 基础命令

### 模型管理

```powershell
# 查看已安装的模型
ollama list
.\ollama list              # 如果ollama没在环境变量中

# 拉取/下载模型
ollama pull deepseek-r1:1.5b
ollama pull qwen2.5:3b
ollama pull phi3:3.8b-mini-4k-instruct-q4_1

# 删除模型
ollama rm <模型名>

# 查看当前正在运行的模型
ollama ps
.\ollama ps
```

### 运行与交互

```powershell
# 运行模型（进入对话界面）
ollama run deepseek-r1:1.5b
.\ollama run deepseek-r1:1.5b

# 停止当前运行的模型
ollama stop deepseek-r1:1.5b
.\ollama stop deepseek-r1:1.5b

# 在对话中使用命令（在 run 界面内）
/set parameter temperature 0.8    # 设置温度
/set context 8192                 # 设置上下文窗口
/exit                             # 退出对话
```

### 服务管理

```powershell
# 启动Ollama服务（解压版）
.\ollama serve

# 查看服务是否运行
curl.exe http://localhost:11434/api/tags
curl.exe http://localhost:11434/api/version

# 彻底退出Ollama（所有进程）
taskkill /F /IM ollama.exe

# 根据PID结束特定进程
taskkill /PID 22376
taskkill /F /PID 22376       # 强制结束
```

---

## 二、GPU 相关命令

### 查看显卡状态

```powershell
# 查看NVIDIA显卡信息（驱动版本、显存使用等）
nvidia-smi

# 更简洁的查看方式（每1秒刷新）
nvidia-smi -l 1

# 查看显卡驱动版本
nvidia-smi --query-gpu=driver_version --format=csv

# 查看显卡温度
nvidia-smi --query-gpu=temperature.gpu --format=csv
```

### 进程和端口

```powershell
# 查看谁占用了某个端口（如11434）
netstat -ano | findstr :11434

# 根据PID查看进程名称
tasklist | findstr 22376

# 查看所有监听端口
netstat -ano | findstr LISTENING
```

---

## 三、环境变量设置

### 临时设置（当前窗口有效）

```powershell
# 设置GPU层数
$env:OLLAMA_GPU_LAYERS=35

# 设置监听地址（允许远程访问）
$env:OLLAMA_HOST="0.0.0.0:11434"

# 设置模型存储路径
$env:OLLAMA_MODELS="D:\ollama\models"

# 允许跨域请求
$env:OLLAMA_ORIGINS="*"

# 设置上下文窗口大小
$env:OLLAMA_CONTEXT_LENGTH=8192

# 设置调试模式（查看详细日志）
$env:OLLAMA_DEBUG=1

# 强制使用CUDA
$env:OLLAMA_LLM_LIBRARY="cuda"

# 一次性设置多个
$env:OLLAMA_GPU_LAYERS=35; $env:OLLAMA_HOST="0.0.0.0:11434"
```

### 查看当前环境变量

```powershell
# 查看所有环境变量
Get-ChildItem Env:

# 查看特定变量
Get-ChildItem Env:OLLAMA_GPU_LAYERS
$env:OLLAMA_GPU_LAYERS
```

---

## 四、防火墙和网络

### 防火墙配置（需管理员权限）

```powershell
# 以管理员身份运行PowerShell

# 开放11434端口（允许入站连接）
New-NetFirewallRule -DisplayName "Allow Ollama Port" -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow

# 删除防火墙规则
Remove-NetFirewallRule -DisplayName "Allow Ollama Port"

# 查看防火墙规则
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*Ollama*"}
```

### 网络测试

```powershell
# 查看本机IP地址
ipconfig

# 测试端口是否开放（从其他机器）
Test-NetConnection <你的IP> -Port 11434

# 本地测试API
curl.exe -X POST http://localhost:11434/api/generate `
  -H "Content-Type: application/json" `
  -d '{\"model\": \"deepseek-r1:1.5b\", \"prompt\": \"你好\", \"stream\": false}'

# 测试API是否运行
curl.exe http://localhost:11434/api/tags
```

---

## 五、WSL 相关命令

### WSL 基础管理（管理员PowerShell）

```powershell
# 停止所有WSL实例
wsl --shutdown

# 查看已安装的WSL发行版
wsl --list --verbose
wsl -l -v

# 设置默认WSL版本
wsl --set-default-version 2

# 更新WSL内核
wsl --update

# 进入默认WSL发行版
wsl

# 进入特定发行版
wsl -d Ubuntu-22.04

# 导出/导入WSL发行版
wsl --export Ubuntu-22.04 D:\backup\ubuntu.tar
wsl --import Ubuntu-22.04 D:\wsl\ubuntu D:\backup\ubuntu.tar
```

### WSL 服务管理

```powershell
# 重启WSL核心服务
Get-Service LxssManager | Restart-Service -Force

# 查看LxssManager服务状态
Get-Service LxssManager
```

### Docker + WSL 问题处理

```powershell
# 彻底关闭Docker和WSL（解决文件占用）
wsl --shutdown
Get-Service LxssManager | Restart-Service -Force

# 如果还有文件占用错误，检查Docker进程
tasklist | findstr docker
taskkill /F /IM "Docker Desktop.exe"
```

---

## 六、文件和路径操作

### 路径导航

```powershell
# 查看当前目录
pwd
Get-Location

# 切换目录
cd C:\Users\roy\ollama
cd ..

# 列出目录内容
ls
dir
Get-ChildItem
```

### 文件和文件夹管理

```powershell
# 删除文件夹（包括所有内容）
Remove-Item -Recurse -Force C:\Users\roy\.ollama

# 创建文件夹
New-Item -ItemType Directory -Path D:\ollama\models

# 查看文件大小
ls C:\Users\roy\.ollama\models -Recurse | Measure-Object -Property Length -Sum

# 复制文件
Copy-Item .\ollama.exe D:\ollama\

# 移动文件
Move-Item .\ollama.exe D:\ollama\
```

### 查看和编辑文件

```powershell
# 查看文件内容（小文件）
Get-Content C:\Users\roy\Desktop\ollama_log.txt

# 实时查看文件更新（类似tail -f）
Get-Content C:\Users\roy\Desktop\ollama_log.txt -Wait

# 用记事本打开
notepad C:\Users\roy\.ollama\config.json

# 输出命令结果到文件
ollama list > C:\Users\roy\Desktop\models.txt
```

---

## 七、系统信息查看

```powershell
# 查看系统信息
systeminfo

# 查看Windows版本
winver

# 查看内存信息
wmic memorychip list

# 查看CPU信息
Get-ComputerInfo | Select-Object CsProcessors

# 查看已安装的程序（检查Ollama是否安装）
winget list | findstr ollama

# 卸载程序
winget uninstall Ollama.Ollama
```

---

## 八、PowerShell 实用技巧

### 常用操作

```powershell
# 清屏
cls
Clear-Host

# 查看命令历史
Get-History

# 获取命令帮助
Get-Help Get-Process
Get-Help netstat -Examples

# 查看别名
Get-Alias

# 创建别名（临时）
Set-Alias ll Get-ChildItem

# 查看PowerShell版本
$PSVersionTable
```

### 管道和过滤

```powershell
# 查找包含特定文本的进程
Get-Process | Where-Object {$_.ProcessName -like "*ollama*"}

# 按内存排序进程
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10

# 查找大文件
Get-ChildItem -Recurse | Where-Object {$_.Length -gt 1GB}
```

---

## 📌 常用组合命令（一键执行）

### 完全重启Ollama服务

```powershell
ollama stop deepseek-r1:1.5b
taskkill /F /IM ollama.exe
$env:OLLAMA_GPU_LAYERS=35
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

### 诊断Ollama状态

```powershell
netstat -ano | findstr :11434
tasklist | findstr ollama
curl.exe http://localhost:11434/api/tags
ollama ps
```

### 清理Docker/WSL文件占用

```powershell
wsl --shutdown
Get-Service LxssManager | Restart-Service -Force
taskkill /F /IM "Docker Desktop.exe" 2>$null
```