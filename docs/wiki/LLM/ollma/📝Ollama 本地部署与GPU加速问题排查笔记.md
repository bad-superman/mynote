# 📝 Ollama 本地部署与GPU加速问题排查笔记

## 一、背景信息

-   **显卡**：NVIDIA GeForce GT 730（4GB 显存）
    
-   **内存**：32GB
    
-   **操作系统**：Windows
    
-   **目标**：本地运行大模型并利用 GPU 加速
    

---

## 二、核心问题与解决方案

### ❓ 问题1：如何查看Ollama是否在使用GPU？

```bash
ollama ps
```

-   `PROCESSOR: 100% CPU` → 未使用GPU
    
-   `PROCESSOR: xx% CPU / xx% GPU` → GPU正在工作（混合模式）
    

### ❓ 问题2：如何强制Ollama使用GPU？

**方法一：临时生效（当前窗口）**

```powershell
$env:OLLAMA_GPU_LAYERS=35
ollama run <模型名>
```

**方法二：永久生效（推荐）**

1.  系统环境变量 → 新建
    
    -   变量名：`OLLAMA_GPU_LAYERS`
        
    -   变量值：`35`
        
2.  重启Ollama服务
    

### ❓ 问题3：nvidia-smi 命令找不到

**原因**：NVIDIA显卡驱动未安装或未正确安装

**解决**：

1.  访问 [NVIDIA官网驱动下载](https://www.nvidia.com/Download/index.aspx)
    
2.  选择型号：GeForce → 700 Series → GT 730 → Windows 10/11 64-bit
    
3.  下载安装，重启电脑
    
4.  验证：`nvidia-smi` 应显示显卡信息
    

### ❓ 问题4：安装驱动后WSL启动不了（错误 ERROR\_SHARING\_VIOLATION）

**原因**：Docker占用了WSL虚拟磁盘文件

**解决**：

```powershell
# 1. 彻底退出Docker Desktop（系统托盘退出）
# 2. 管理员PowerShell执行：
wsl --shutdown
Get-Service LxssManager | Restart-Service -Force
# 3. 重新启动WSL
wsl
```

### ❓ 问题5：Ollama下载哪个版本？

从GitHub Releases下载：

-   ✅ NVIDIA显卡 → `ollama-windows-amd64.zip`（完整版，包含CUDA支持）
    
-   ❌ 不要用 `ollama-windows-amd64-rocm.zip`（AMD显卡专用）
    
-   ⚠️ `OllamaSetup.exe` 可能自动安装纯CPU版
    

### ❓ 问题6：PowerShell中无法直接运行 `ollama` 命令

**原因**：PowerShell安全策略，默认不运行当前目录程序

**解决**：

-   临时：`.\ollama <命令>`
    
-   永久：将Ollama路径（如 `C:\Users\roy\ollama`）添加到系统环境变量 `Path` 中
    

### ❓ 问题7：如何远程调用本地Ollama？

**步骤1：设置监听地址**

```powershell
# 环境变量
OLLAMA_HOST=0.0.0.0:11434
```

**步骤2：开放防火墙**

```powershell
# 管理员PowerShell
New-NetFirewallRule -DisplayName "Allow Ollama" -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow
```

**步骤3：允许跨域（如需Web调用）**

```powershell
OLLAMA_ORIGINS=*
```

**步骤4：其他设备调用**

```bash
curl http://<你的IP>:11434/api/generate -d '{"model": "模型名", "prompt": "你好"}'
```

⚠️ **安全警告**：Ollama无身份验证，暴露公网有风险。建议局域网使用或配合VPN/SSH隧道。

### ❓ 问题8：Ollama有没有配置文件？

Ollama**没有集中配置文件**，主要通过：

-   **环境变量**：服务配置（如 `OLLAMA_HOST`、`OLLAMA_GPU_LAYERS`）
    
-   **Modelfile**：模型定制（参数、系统提示词等）
    
-   `/set`**命令**：运行时临时调整
    

常用环境变量：

| 变量名 | 作用  | 示例  |
| --- | --- | --- |
| `OLLAMA_HOST` | 监听地址 | `0.0.0.0:11434` |
| `OLLAMA_MODELS` | 模型存储路径 | `D:\ollama\models` |
| `OLLAMA_GPU_LAYERS` | GPU加载层数 | `35` |
| `OLLAMA_ORIGINS` | 跨域允许 | `*` |
| `OLLAMA_CONTEXT_LENGTH` | 上下文窗口 | `8192` |

### ❓ 问题9：Ollama如何后台运行？

-   **安装版**：自动作为Windows服务后台运行
    
-   **解压版**：专门开一个PowerShell窗口运行 `.\ollama serve`（保持窗口开启）
    
-   **注册为服务**：可用NSSM将 `ollama serve` 注册为Windows服务
    

---

## 三、验证GPU是否工作的方法

1.  **ollama ps**：查看 `PROCESSOR` 列是否为 `CPU/GPU` 混合
    
2.  **任务管理器**：查看GPU 1（GT 730）利用率是否跳动
    
3.  **nvidia-smi**：查看显存占用是否有变化
    

---

## 四、推荐模型（基于GT 730 4GB + 32GB内存）

| 目标  | 模型  | 说明  |
| --- | --- | --- |
| GPU加速最优 | `qwen2.5:3b`、`phi3:3.8b` | 3-4B模型，基本能完全放进显存 |
| 平衡体验 | `qwen2.5:7b`、`deepseek-v2:16b` | 7-16B，混合模式运行 |
| 超大模型（纯CPU） | `qwen2.5:72b`、`llama3:70b` | 70B量化版，依赖32GB内存 |

---

## 五、常用命令速查

```powershell
# 查看已安装模型
ollama list

# 拉取模型
ollama pull <模型名>

# 运行模型
ollama run <模型名>

# 查看当前运行的模型
ollama ps

# 停止模型
ollama stop <模型名>

# 查看ollama服务状态
curl http://localhost:11434/api/tags

# 设置GPU层数（临时）
$env:OLLAMA_GPU_LAYERS=35
```

---

## 六、环境变量

以下是将您提供的 Ollama 环境变量梳理成的 Markdown 表格：

| 环境变量 | 描述  | 默认值 |
| --- | --- | --- |
| `OLLAMA_DEBUG` | 显示额外的调试信息。 | (例如: `OLLAMA_DEBUG=1`) |
| `OLLAMA_HOST` | Ollama 服务器的 IP 地址和端口。 | `127.0.0.1:11434` |
| `OLLAMA_KEEP_ALIVE` | 模型在内存中保持加载的时长。 | `"5m"` (5分钟) |
| `OLLAMA_MAX_LOADED_MODELS` | 每个 GPU 上最大加载模型数量。 | (未指定) |
| `OLLAMA_MAX_QUEUE` | 请求队列的最大长度。 | (未指定) |
| `OLLAMA_MODELS` | 模型目录的存储路径。 | (未指定) |
| `OLLAMA_NUM_PARALLEL` | 最大并行请求处理数量。 | (未指定) |
| `OLLAMA_NOPRUNE` | 启动时不修剪模型 blob。 | (未指定) |
| `OLLAMA_ORIGINS` | 允许的源列表（跨域请求），使用逗号分隔。 | (未指定) |
| `OLLAMA_SCHED_SPREAD` | 始终跨所有 GPU 调度模型。 | (未指定) |
| `OLLAMA_TMPDIR` | 临时文件的存放位置。 | (未指定) |
| `OLLAMA_FLASH_ATTENTION` | 启用 Flash Attention 以优化计算。 | (未指定) |
| `OLLAMA_LLM_LIBRARY` | 设置 LLM 库以绕过自动检测。 | (未指定) |

## 遇到的问题

1.  有独立显卡但是模型没用上
    

先排查网卡驱动是否正常，或升级到最新网卡

查看**ollama server**日志中CUDA\_VISIBLE\_DEVICES是否有设备，有的话就可以了

但是我本地的显卡太老了，不支持CUDA12\\13，只支持11，通过设置\*\*OLLAMA\_LLM\_LIBRARY="vulkan"\*\*和\*\*OLLAMA\_LLM=1"\*\*强制使用vulkan后端就可以使用GPUk了

🎯 Vulkan 是什么？ Vulkan 是一种底层图形和计算 API（应用程序编程接口），可以理解为“显卡的通用语言”。

| API | 类比  | 特点  |
| --- | --- | --- |
| **CUDA** | 英式英语 | NVIDIA 的专属语言，说得最流利，但只有 NVIDIA 显卡懂 |
| **Vulkan** | 世界语 | 所有显卡都懂的国际语言，但说得没那么流利 |
| **DirectX** | 中文  | Windows 系统默认语言，游戏常用 |
| **OpenGL** | 法语  | 老牌语言，曾经很流行 |