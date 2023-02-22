##### 查询表状态

```
mysql> SHOW TABLE STATUS like 'contact_30'\G
*************************** 1. row ***************************
           Name: contact_30
         Engine: InnoDB
        Version: 10
     Row_format: Dynamic
           Rows: 609024
 Avg_row_length: 99
    Data_length: 60456960
Max_data_length: 0
   Index_length: 227622912
      Data_free: 4194304
 Auto_increment: 4530020
    Create_time: 2021-01-14 22:33:19
    Update_time: 2022-09-27 11:59:45
     Check_time: NULL
      Collation: utf8_general_ci
       Checksum: NULL
 Create_options: row_format=DYNAMIC
        Comment:
1 row in set (0.00 sec)
```

Row_format: 数据格式。
Rows 表数据行数，MyISAM的这个数据行数统计是准确的，而InnoDB是估值是不准确的。这里t_user表的预估行数是9964行。
Data_length: 该表所占用空间的字节数。 60456960 bytes = 59040kb 

### SQL执行成本分析

[成本分析](https://www.cnblogs.com/zhuwenjoyce/p/14968183.html)

1. 计算全表扫描的查询索引

mysql每页存储16kb，innoDB需要59040kb / 16=3690页磁盘来存储

磁盘io成本 = 3690*1.0(磁盘io成本) + 1.1(微调系数) = 3691.1

cpu成本 = 609024(rows)*0.2 + 0.01(微调系数) = 121804.81

全表扫描成本 = 3691.1 + 121805.8 = 125496.9

2. 计算走索引的查询成本

mysql规定，当读取索引时，每扫描一个扫描区间或者范围区间的IO成本，和读取一个页面的IO成本是一样的，都是1.0

* 查看执行计划

```
mysql> explain select id from contact_30 where uid = 32216965 and type = 1 and risk = 0 and status = 0 and version_id > 0 and version_id < 1664194189167313 and tag&8 order by rank desc, version_id desc limit 500;
+----+-------------+------------+------------+------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------+---------+-------------------------+-------+----------+--------------------------+
| id | select_type | table      | partitions | type | possible_keys                                                                                                                                                                          | key                                          | key_len | ref                     | rows  | filtered | Extra                    |
+----+-------------+------------+------------+------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------+---------+-------------------------+-------+----------+--------------------------+
|  1 | SIMPLE      | contact_30 | NULL       | ref  | owner_peer_conv_type,owner_id_version_id_del_status_key,idx_owner_conv_type_del_status_version_id,idx_uid_type_risk_status_rank_version_id_tag,idx_uid_risk_status_rank_version_id_tag | idx_uid_type_risk_status_rank_version_id_tag | 14      | const,const,const,const | 18266 |    11.11 | Using where; Using index |
+----+-------------+------------+------------+------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------------------------------------+---------+-------------------------+-------+----------+--------------------------+
1 row in set, 1 warning (0.01 sec)
```

io成本

sql扫描了18266行，

每个索引值重复行数平均值：609024(Rows) / 13370(Cardinality) = 45.55

18266 / 45.55 * 1.0 = 401 + 4(扫描了4个范围区间)

cpu成本

18266  * 0.1111 * 0.2 + 0.01 = 405.88



回表成本

回表IO成本 = 18266  * 0.1111 * 1.0 + 1.0 = 2030.35 

回表cpu成本 = 18266  * 0.1111 * 0.2 = 405.87

* 查看索引信息

```
mysql> show index from contact_30 where Key_name="idx_uid_type_risk_status_rank_version_id_tag";
+------------+------------+----------------------------------------------+--------------+-------------+-----------+-------------+----------+--------+------+------------+---------+---------------+
| Table      | Non_unique | Key_name                                     | Seq_in_index | Column_name | Collation | Cardinality | Sub_part | Packed | Null | Index_type | Comment | Index_comment |
+------------+------------+----------------------------------------------+--------------+-------------+-----------+-------------+----------+--------+------+------------+---------+---------------+
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            1 | uid         | A         |        7859 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            2 | type        | A         |        8818 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            3 | risk        | A         |        7092 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            4 | status      | A         |       13478 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            5 | rank        | A         |       13370 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            6 | version_id  | A         |      542032 |     NULL | NULL   |      | BTREE      |         |               |
| contact_30 |          1 | idx_uid_type_risk_status_rank_version_id_tag |            7 | tag         | A         |      518613 |     NULL | NULL   |      | BTREE      |         |               |
+------------+------------+----------------------------------------------+--------------+-------------+-----------+-------------+----------+--------+------+------------+---------+---------------+
7 rows in set (0.00 sec)
```

