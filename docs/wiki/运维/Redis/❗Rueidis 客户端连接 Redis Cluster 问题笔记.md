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
    

### 结论

上面是ai分析的结构，真正的问题是Rueidis v1.0.54 有bug, 在发送HELLO命令之前没有AUTH，更新Rueidis版本就可以了笑脸😁

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