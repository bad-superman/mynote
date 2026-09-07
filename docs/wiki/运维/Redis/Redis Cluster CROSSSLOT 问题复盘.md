# Redis Cluster CROSSSLOT 问题复盘

## 背景

某次生产配置从 Redis 单机形态调整为 Redis Cluster + TLS 后，连接层问题解决以后，运行期又暴露了 `CROSSSLOT`。

这个问题和具体业务无关，本质是原代码里存在单机 Redis 假设：

- 用一条 Lua 脚本同时读写多个独立 key。
- 用 `MGET` 一次读取多个独立 key。
- 这些 key 在 Redis Cluster 下不保证落到同一个 slot。

## 现象

Redis Cluster 返回类似错误：

```text
CROSSSLOT Keys in request don't hash to the same slot
```

常见触发命令：

```redis
MGET obj:a:1 obj:b:1 obj:c:1
EVAL "<lua>" 3 obj:a:1 obj:b:1 obj:c:1 ...
```

在单机 Redis 中，这类命令通常可以工作；切到 Redis Cluster 后，只要多个 key 分布在不同 slot，命令就会失败。

## 根因

Redis Cluster 按 key 计算 slot。单条多 key 命令只有在所有 key 属于同一个 slot 时才允许执行。

Lua 脚本也遵守这个限制：`EVAL` 传入的 `KEYS` 如果跨 slot，就会报 `CROSSSLOT`。

可以用下面的命令检查 key slot：

```bash
redis-cli -c CLUSTER KEYSLOT 'obj:a:1'
redis-cli -c CLUSTER KEYSLOT 'obj:b:1'
```

如果输出不同，说明这些 key 不能放进同一条多 key 命令。

## 修复思路

### 1. 同一对象的多个属性改成 Hash

如果多个 key 本来描述的是同一个对象的不同字段，优先合并成一个 hash key。

修改前：

```text
obj:field_a:{id}
obj:field_b:{id}
obj:field_c:{id}
```

修改后：

```text
obj:{id}
  field_a
  field_b
  field_c
```

写入时只操作一个 key：

```redis
HSET obj:{id} field_a value_a field_b value_b field_c value_c
EXPIRE obj:{id} 300
```

读取时：

```redis
HMGET obj:{id} field_a field_b field_c
```

如果需要原子校验和写入，可以继续用 Lua，但 `KEYS` 只传一个 hash key。

### 2. 多个对象批量读取改 Pipeline

如果要读取多个对象，每个对象一个 hash key，不要用一条跨 key 的 `MGET`。

可以改为 pipeline 多条单 key 命令：

```text
Pipeline:
  HMGET obj:{id1} field_a field_b
  HMGET obj:{id2} field_a field_b
  HMGET obj:{id3} field_a field_b
```

Pipeline 只是减少网络往返，不要求所有 key 同 slot。

### 3. 必须多 key 原子操作时使用 Hash Tag

如果确实需要一条命令原子操作多个 key，可以使用 Redis Cluster hash tag，让多个 key 按 `{...}` 中的内容计算 slot。

```text
obj:{account_1}:a
obj:{account_1}:b
obj:{account_1}:c
```

上面三个 key 会落到同一个 slot。

注意：hash tag 会影响 slot 分布，不能为了省事把大量热点 key 都塞进同一个 tag。

## 容易踩坑

### 旧 key 类型冲突

如果旧版本中某个 key 是 string，新版本想复用同名 key 改成 hash，旧 key 未过期前会触发类型错误：

```text
WRONGTYPE Operation against a key holding the wrong kind of value
```

稳妥做法：

- 新 hash 使用新 key 名。
- 或先做迁移脚本。
- 或确认旧 key TTL 足够短，并安排兼容窗口。

### Lua 脚本不是绕过 Cluster 限制的办法

Lua 能保证脚本内逻辑原子，但不能让跨 slot key 合法。

错误示例：

```redis
EVAL "<lua>" 2 obj:a:1 obj:b:1
```

正确方向：

- 调整成单 key hash。
- 或给相关 key 使用同一个 hash tag。
- 或拆成多条命令并接受非全局原子。

### Cluster 客户端支持不等于业务命令安全

客户端能连接 Redis Cluster，只代表拓扑、重定向、TLS、认证等连接层打通了。

业务命令仍然需要逐个检查：

- `MGET` / `MSET`
- `DEL key1 key2 ...`
- `EXISTS key1 key2 ...`
- `EVAL` / `EVALSHA`
- 其他多 key 命令

## 验证清单

1. 检查所有多 key 命令是否跨 slot。

```bash
rg -n "MGet|MSet|Del\\(|Exists\\(|Eval|EvalSha|Pipeline|Pipelined" .
```

2. 对关键 key 做 slot 验证。

```bash
redis-cli -c CLUSTER KEYSLOT 'obj:{id1}'
redis-cli -c CLUSTER KEYSLOT 'obj:{id2}'
```

3. 本地或测试环境使用 Redis Cluster 跑最小回归。

```bash
go test ./...
```

4. 线上灰度时关注：

- `CROSSSLOT`
- `MOVED` / `ASK`
- `WRONGTYPE`
- Redis 命令耗时
- pipeline 批量大小和超时

## 回退

优先保留旧读取路径的短期兼容能力：

- 新写入走新 key。
- 读取先读新 key，缺失时可短期回退旧 key。
- 旧 key 自然过期或迁移完成后，再删除兼容逻辑。

如果 Cluster 改造只完成了连接层，业务命令还没完成排查，不要直接把生产流量全部切到 Cluster。
