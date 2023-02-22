## 查询优化器优化trace

```
mysql> set session optimizer_trace="enabled=on",end_markers_in_json=on;
Query OK, 0 rows affected (0.00 sec)
 
mysql> SELECT id FROM `contact_26`WHERE (uid = '45549227') AND (type = '1') AND (risk = '0') AND (status = '0') AND (version_id > '1645962030000070') AND (tag&'2') ORDER BY rank desc,version_id desc LIMIT 9007199254740992;
+---------+
| id      |
+---------+
| 3615097 |
+---------+
1 row in set (0.01 sec)
 
mysql> SELECT * FROM information_schema.OPTIMIZER_TRACE;
mysql> set session optimizer_trace="enabled=off";
Query OK, 0 rows affected (0.00 sec)
```

## SHOW STATUS

[相关链接](https://fromdual.com/mysql-handler-read-status-variables)

[相关链接](https://juejin.cn/post/6850418109329702920)

show status查询mysql服务状态的计数，有的变量是全局的，有的变量的session级别的

1. show status like 'handler_read%';

```
mysql> SHOW SESSION STATUS LIKE 'handler_read%';
+-----------------------+-------+
| Variable_name         | Value |
+-----------------------+-------+
| Handler_read_first    | 0     |
| Handler_read_key      | 3     |
| Handler_read_last     | 0     |
| Handler_read_next     | 0     |
| Handler_read_prev     | 10114 |
| Handler_read_rnd      | 0     |
| Handler_read_rnd_next | 103   |
+-----------------------+-------+
7 rows in set (0.00 sec)
```

* Handler_read_first    读取索引第一个元素的次数，如果value比较高，说明存在很多全索引扫描
* Handler_read_last    读取索引最后一个元素的次数
* Handler_read_key    根据索引读取的操作次数
* Handler_read_next   按照索引向后读取行数，如果查询的索引范围过大、或者正在进行索引扫描，value会增高
* Handler_read_prev   按照索引向前读取行数
* Handler_read_rnd   
* Handler_read_rnd_next 

## SHOW PROFILELIST



## SHOW PROFILE

1. 开启查看系统性能

```
## 开启
mysql> select @@profiling;
+-------------+
| @@profiling |
+-------------+
|           0 |
+-------------+
1 row in set, 1 warning (0.01 sec)

mysql> set profiling=ON;
Query OK, 0 rows affected, 1 warning (0.00 sec)

mysql> select @@profiling;
+-------------+
| @@profiling |
+-------------+
|           1 |
+-------------+
1 row in set, 1 warning (0.00 sec)
## 关闭
mysql> set profiling=OFF;
Query OK, 0 rows affected, 1 warning (0.00 sec)
```

2. 执行查询语句

3. 查看sql执行情况

* 查看执行记录

```
mysql> show profiles;
+----------+------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Query_ID | Duration   | Query                                                                                                                                                                                                                                                                                                        |
+----------+------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|        1 | 0.00011125 | select @@profiling
```

* 查看sql详情

```
mysql> show profile for query 2;
+----------------------+----------+
| Status               | Duration |
+----------------------+----------+
| starting             | 0.000073 |
| checking permissions | 0.000008 |
| checking permissions | 0.000005 |
| Opening tables       | 0.000052 |
| init                 | 0.000036 |
| System lock          | 0.000005 |
| optimizing           | 0.000004 |
| optimizing           | 0.000008 |
| statistics           | 0.010685 |
| preparing            | 0.000032 |
| Sorting result       | 0.000008 |
| statistics           | 0.000017 |
| preparing            | 0.000007 |
| executing            | 0.000006 |
| Sending data         | 0.000019 |
| executing            | 0.000004 |
| Sending data         | 0.041649 |
| end                  | 0.000021 |
| query end            | 0.000014 |
| closing tables       | 0.000004 |
| removing tmp table   | 0.000008 |
| closing tables       | 0.000009 |
| freeing items        | 0.000027 |
| cleaning up          | 0.000005 |
+----------------------+----------+
24 rows in set, 1 warning (0.00 sec)
```

默认是执行时间，在profile可以添加指标

* cpu
* memory
* block io

## SHOW VARIABLES

* SHOW VARIABLES LIKE '%XXX%';
* SHOW GLOBAL VARIABLES LIKE '%XXX%';

## SHOW STATUS

* SHOW GLOBAL STATUS;
* SHOW SESSION STATUS;



