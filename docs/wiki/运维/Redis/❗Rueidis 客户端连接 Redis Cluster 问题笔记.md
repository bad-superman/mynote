# Rueidis 客户端连接 Redis Cluster 问题笔记

## 问题背景

在使用 rueidis 客户端连接 Redis Cluster 时遇到 `NOAUTH Authentication required` 错误，即使配置了正确的密码。

## 遇到的问题

### 问题 1: NOAUTH Authentication required

**现象**：配置了密码但连接 Redis Cluster 时仍然报认证错误

**原因**：rueidis 在 Cluster 模式下会尝试自动检测集群拓扑，但在某些 Redis Cluster 配置下，认证信息可能无法正确传递到所有节点。

**解决方案**：使用 `ForceSingleClient: true` 强制使用单机客户端模式。

```go
client, err := rueidis.NewClient(rueidis.ClientOption{
    InitAddress:       []string{"10.213.64.8:6379"},
    Password:          "your-password",
    ForceSingleClient: true,
    DisableCache:      true,  // 必须同时设置
})
```

### 问题 2: CLIENT TRACKING ON OPTIN 错误

**错误信息**：

```text
ClientOption.DisableCache must be true for redis not supporting client-side caching or not supporting RESP3
```

**原因**：

-   rueidis 默认启用客户端缓存（client-side caching）功能
    
-   该功能需要 Redis 支持 RESP3 协议和 CLIENT TRACKING 命令
    
-   如果 Redis 不支持这些特性，必须设置 `DisableCache: true`
    

---

## ForceSingleClient 对集群连接的影响

### ForceSingleClient = false (默认)

rueidis 会自动检测 Redis 是单机还是集群模式：

1.  连接 InitAddress 中的节点
    
2.  执行 `CLUSTER SLOTS` 命令获取集群拓扑
    
3.  如果返回集群信息，则使用集群客户端模式
    
4.  如果不是集群，则降级为单机模式
    

**优点**：

-   自动适应集群拓扑变化
    
-   支持多节点分布式读写
    
-   性能更好（请求可以分发到多个节点）
    

**缺点**：

-   需要 Redis 支持 CLUSTER 命令
    
-   认证信息需要在集群拓扑扫描时正确传递
    
-   某些网络环境下可能无法正确获取拓扑
    

### ForceSingleClient = true

强制使用单机客户端模式，即使连接的是 Redis Cluster：

1.  只连接到 InitAddress 指定的节点
    
2.  不执行 CLUSTER SLOTS 命令
    
3.  所有请求都通过这一个节点转发
    

**优点**：

-   简单可靠，避免集群拓扑检测问题
    
-   适用于某些特殊的集群配置（如通过代理访问）
    
-   认证逻辑更简单
    

**缺点**：

-   **失去集群的分布式优势**：所有请求都通过单个节点
    
-   **性能瓶颈**：该节点成为流量入口，可能成为瓶颈
    
-   **拓扑感知缺失**：无法感知集群拓扑变化，如果该节点宕机需要手动切换
    

### 对 Centrifugo 的影响

对于 Centrifugo 的 presence\_manager 使用场景：

-   **读写模式**：主要是 presence 信息的读写，数据量不大
    
-   **访问模式**：按 channel 哈希到特定 slot，即使单机客户端也会路由到正确节点
    

因此使用 `ForceSingleClient: true` 对性能影响有限，是可以接受的方案。

---

## RESP3 协议

### 什么是 RESP3

RESP (Redis Serialization Protocol) 是 Redis 的客户端 - 服务器通信协议。

| 版本  | 发布年份 | 主要特性 |
| --- | --- | --- |
| RESP2 | 2012 | 基础数据类型（字符串、数组、整数、错误、空） |
| RESP3 | 2018 | 新增数据类型、客户端缓存支持、更好的错误处理 |

### RESP3 新增特性

1.  **新的数据类型**：
    
    -   Push 消息（服务器主动推送）
        
    -   Map 类型（原为数组）
        
    -   Set 类型
        
    -   Double 类型
        
    -   Boolean 类型
        
2.  **客户端缓存支持**：
    
    -   `CLIENT TRACKING` 命令
        
    -   服务器可以通知客户端缓存失效
        
3.  **更好的错误处理**：
    
    -   更详细的错误信息
        
    -   错误分类
        

### 如何检查 Redis 是否支持 RESP3

```bash
redis-cli HELLO
```

返回包含 `proto` 字段：

```text
1) "server"
2) "redis"
...
7) "proto"
8) (integer) 3    # 3 表示支持 RESP3
```

### rueidis 与 RESP3

rueidis 默认尝试使用 RESP3：

-   如果 Redis 支持 RESP3，则使用 RESP3
    
-   否则降级到 RESP2
    

可以通过 `AlwaysRESP2: true` 强制使用 RESP2。

---

## Client-Side Caching (客户端缓存)

### 什么是客户端缓存

Redis 客户端缓存是一种优化机制，允许客户端在本地缓存从服务器读取的数据，同时服务器会跟踪客户端的缓存并在数据变更时通知客户端失效。

### 工作原理

```text
┌─────────────┐                    ┌─────────────┐
│   Client    │                    │   Server    │
│  (rueidis)  │                    │   (Redis)   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ 1. 读取 key                      │
       │─────────────────────────────────>│
       │                                  │ 记录客户端
       │                                  │ 跟踪的 key
       │ 2. 返回数据 + 启用 TRACKING      │
       │<─────────────────────────────────│
       │                                  │
       │ (缓存数据)                       │
       │                                  │
       │                                  │ key 被修改
       │ 3. 推送失效通知                  │
       │<─────────────────────────────────│
       │ 删除缓存                         │
```

### 启用条件

客户端缓存需要：

1.  **Redis 6.0+** (引入 CLIENT TRACKING 命令)
    
2.  **RESP3 协议** (需要 Push 消息支持)
    
3.  rueidis 的 `DisableCache: false` (默认)
    

### 为什么需要 DisableCache: true

当 Redis 不支持 RESP3 或 CLIENT TRACKING 时：

-   rueidis 无法启用客户端缓存
    
-   但 `ForceSingleClient` 模式下仍尝试使用缓存功能
    
-   导致错误：`CLIENT TRACKING ON OPTIN`
    

**解决方案**：设置 `DisableCache: true` 禁用客户端缓存功能。

### 性能影响

禁用客户端缓存的影响：

-   **增加网络请求**：每次读取都需要访问 Redis
    
-   **增加延迟**：无法利用本地缓存
    

---

### 检查清单

- [ ] Redis 版本是否 >= 6.0 (支持 CLIENT TRACKING) <!-- div-format -->

- [ ] Redis 是否支持 RESP3 (`redis-cli HELLO` 检查 proto) <!-- div-format -->

- [ ] 网络是否允许 CLUSTER SLOTS 命令 <!-- div-format -->

- [ ] 是否需要分布式性能（如果不需要，ForceSingleClient 是安全的选择） <!-- div-format -->

---

## 参考链接

-   [rueidis GitHub](https://github.com/redis/rueidis)
    
-   [Redis RESP3 规范](https://github.com/antirez/RESP3/blob/master/spec.md)
    
-   [Redis 客户端缓存文档](https://redis.io/docs/manual/client-side-caching/)
    
-   [CLIENT TRACKING 命令](https://redis.io/commands/client-tracking/)