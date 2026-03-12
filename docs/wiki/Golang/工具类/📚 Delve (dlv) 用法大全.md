## 📚 Delve (dlv) 用法大全

### 一、基础调试命令

#### 1.1 直接调试模式

```bash
# 最基本的调试方式（在我们的环境中失败）
dlv debug main.go

# 调试当前包
dlv debug .

# 指定文件调试
dlv debug main.go -- -arg1 value
```

#### 1.2 Headless 模式（成功工作的方式）

```bash
# 基础 headless 模式
dlv debug --headless --listen=:2345 --api-version=2 main.go

# 带日志的 headless 模式
dlv debug --headless --listen=:2345 --api-version=2 --accept-multiclient --log --log-output=dap main.go

# 启动后继续执行
dlv debug --headless --listen=:2345 --api-version=2 --accept-multiclient --continue main.go
```

#### 1.3 Exec 模式（调试已编译程序）

```bash
# 先编译
go build -gcflags="all=-N -l" -o /tmp/debug_bin .

# 调试二进制文件
dlv exec /tmp/debug_bin
dlv exec --headless --listen=:2345 /tmp/debug_bin
```

#### 1.4 Attach 模式（附加到运行中的进程）

```bash
# 查找进程 PID
pgrep your-program

# 附加到进程
dlv attach <PID>
dlv attach --headless --listen=:2345 <PID>
```

### 二、Delve DAP 模式（最新协议）

```bash
# 启动 DAP 服务器
dlv dap --listen=:23456

# 带日志的 DAP 模式
dlv dap --listen=:23456 --log --log-output=dap

# 通过命令行加载程序
curl -X POST -H "Content-Type: application/json" -d '{
  "name": "attach",
  "mode": "debug",
  "program": "/path/to/your/project"
}' http://localhost:23456/launch
```

### 三、调试器后端选择

```bash
# 列出可用后端
dlv debug --help | grep -A5 backend

# 使用不同后端
dlv debug --backend=native main.go      # 原生后端
dlv debug --backend=default main.go      # 默认后端
dlv debug --backend=llvm main.go         # LLVM 后端
dlv debug --backend=lldb main.go         # LLDB 后端（macOS）
```

### 四、日志和调试信息

```bash
# 启用各种日志输出
dlv debug --log --log-output=debugger main.go
dlv debug --log --log-output=rpc main.go
dlv debug --log --log-output=dap main.go
dlv debug --log --log-output=debugger,rpc,dap,terminal main.go

# 将日志输出到文件
dlv debug --log --log-output=debugger --log-dest=/tmp/dlv.log main.go
```

### 五、交互式调试中的断点命令

#### 5.1 在 dlv 控制台中设置断点

```bash
# 进入 dlv 交互式控制台
dlv debug main.go

# 然后在 (dlv) 提示符下：
```

**基本断点命令：**

```bash
# 在指定行号打断点
(dlv) break main.go:10
(dlv) b main.go:10          # b 是 break 的简写

# 在函数名打断点
(dlv) break main.main
(dlv) break main.init
(dlv) break fmt.Println

# 在方法上打断点
(dlv) break (*MyStruct).String

# 在当前文件当前行+5行打断点
(dlv) break +5
(dlv) break -3

# 根据条件打断点
(dlv) break main.go:10 if i == 5
(dlv) break main.main if x > 100 && y < 50
```

#### 5.2 查看和管理断点

```bash
# 列出所有断点
(dlv) breakpoints
(dlv) bp                    # bp 是简写

# 输出示例：
Breakpoint 1 at 0x123456 for main.main() main.go:5 (0 hits)
Breakpoint 2 at 0x123789 for main.main() main.go:10 (2 hits)

# 删除断点
(dlv) clear 1               # 删除断点1
(dlv) clear main.go:10      # 删除指定位置的断点
(dlv) clearall              # 删除所有断点
(dlv) clearall main.go      # 删除文件中的所有断点

# 禁用/启用断点
(dlv) toggle 1              # 切换断点1的状态
(dlv) enable 1              # 启用断点1
(dlv) disable 2             # 禁用断点2
```

### 六、headless 模式下的断点设置

#### 6.1 通过命令行客户端

```bash
# 终端1：启动 headless 服务
dlv debug --headless --listen=:2345 --api-version=2 --accept-multiclient main.go

# 终端2：连接客户端
dlv connect localhost:2345

# 然后在客户端中设置断点
(dlv) break main.go:15
(dlv) continue
```

#### 6.2 通过 REST API

```bash
# 启动 headless 服务
dlv debug --headless --listen=:2345 --api-version=2 --accept-multiclient main.go

# 通过 API 设置断点
curl -X POST http://localhost:2345/breakpoint \
  -H "Content-Type: application/json" \
  -d '{
    "breakpoint": {
      "file": "main.go",
      "line": 15
    }
  }'
```

### 七、高级断点类型

#### 7.1 条件断点

```bash
# 只有满足条件时才暂停
(dlv) condition 1 i == 10
(dlv) cond 2 err != nil    # cond 是 condition 的简写

# 查看断点条件
(dlv) condition 1
```

#### 7.2 函数断点

```bash
# 在正则表达式匹配的所有函数上打断点
(dlv) break main.*Handler

# 在递归函数上打断点（只在第一次进入时暂停）
(dlv) break -r main.recursive 1
```

#### 7.3 跟踪点（Tracepoint）

```bash
# 不暂停，只打印信息
(dlv) trace main.go:15
(dlv) trace fmt.Println

# 自定义跟踪输出
(dlv) trace main.go:15 "i = {{.i}}"
```

#### 7.4 数据断点（Watchpoint）

```bash
# 监视变量何时被修改
(dlv) watch -w globalVar   # 写入时暂停
(dlv) watch -r globalVar   # 读取时暂停
(dlv) watch -rw globalVar  # 读写都暂停
```

### 八、断点调试实战

#### 8.1 示例程序

```go
package main

import "fmt"

func main() {
    fmt.Println("Starting...")
    
    for i := 0; i < 10; i++ {
        process(i)
    }
    
    fmt.Println("Done!")
}

func process(n int) {
    result := n * n
    fmt.Printf("Processing %d: %d\n", n, result)
}
```

#### 8.2 调试会话示例

```bash
$ dlv debug main.go
(dlv) break main.go:7                # 在 for 循环行打断点
(dlv) break main.go:12               # 在 process 函数内打断点
(dlv) break process if n == 5        # 条件断点，只在 n=5 时暂停
(dlv) breakpoints                     # 查看所有断点

Breakpoint 1 at 0x123456 for main.main() main.go:7 (0 hits)
Breakpoint 2 at 0x123789 for main.process() main.go:12 (0 hits)
Breakpoint 3 at 0x123abc for main.process() main.go:12 (0 hits) (condition n == 5)

(dlv) continue                         # 运行到第一个断点
> main.main() main.go:7 (hits goroutine(1):1 total:1)
     6: func main() {
     7:     for i := 0; i < 10; i++ {
     8:         process(i)
     9:     }

(dlv) print i                          # 查看变量
0

(dlv) continue                         # 继续运行
> main.process() main.go:12 (hits goroutine(1):1 total:1)
    11: func process(n int) {
    12:     result := n * n
    13:     fmt.Printf("Processing %d: %d\n", n, result)
    14: }

(dlv) next                             # 单步执行
> main.process() main.go:13 (hits goroutine(1):1 total:1)
    12:     result := n * n
    13:     fmt.Printf("Processing %d: %d\n", n, result)
    14: }

(dlv) print n                           # 查看参数
0
(dlv) print result                       # 查看计算结果
0
```

### 九、断点调试最佳实践

#### 9.1 临时断点

```bash
# 运行到光标位置（一次性断点）
(dlv) until main.go:20
```

#### 9.2 断点日志

```bash
# 添加断点时直接设置条件
(dlv) break main.go:15 if i%2==0

# 设置断点命中时的操作
(dlv) on 1 print i
(dlv) on 1 list
(dlv) on 1 stack
```

#### 9.3 断点统计

```bash
# 查看断点命中次数
(dlv) break -c 5 main.go:15  # 在第5次命中时才暂停

# 重置断点命中计数
(dlv) clear 1
(dlv) break main.go:15       # 重新设置
```