# 🐼 Python Pandas 完全教程

Pandas 是 Python 数据科学的核心库，提供了快速、灵活、易用的数据结构。以下是完整的使用教程：

## 📦 **1\. 安装与环境配置**

### **安装 Pandas**

```bash
# 基础安装
pip install pandas

# 完整数据科学环境
pip install pandas numpy matplotlib scikit-learn

# 特定版本
pip install pandas==2.1.0

# 通过 conda
conda install pandas
```

### **导入约定**

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 设置显示选项
pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.max_rows', 100)       # 最多显示100行
pd.set_option('display.width', 1000)         # 显示宽度
pd.set_option('display.float_format', '{:.2f}'.format)  # 浮点数格式
```

## 🏗️ **2\. 核心数据结构**

### **Series - 一维数组**

```python
# 创建 Series
s1 = pd.Series([1, 3, 5, np.nan, 6, 8])
s2 = pd.Series([10, 20, 30], index=['a', 'b', 'c'])
s3 = pd.Series({'a': 1, 'b': 2, 'c': 3})

print(s1)
print(f"类型: {type(s1)}")
print(f"值: {s1.values}")
print(f"索引: {s1.index}")

# Series 操作
print(s2 * 2)                    # 标量运算
print(s2[s2 > 15])               # 布尔索引
print(s2.get('d', default=0))    # 安全获取
```

### **DataFrame - 二维表格**

```python
# 创建 DataFrame
# 方法1：从字典创建
df1 = pd.DataFrame({
    '姓名': ['张三', '李四', '王五', '赵六'],
    '年龄': [25, 30, 35, 28],
    '城市': ['北京', '上海', '广州', '深圳'],
    '工资': [50000, 60000, 55000, 65000]
})

# 方法2：从列表创建
data = [
    ['张三', 25, '北京', 50000],
    ['李四', 30, '上海', 60000],
    ['王五', 35, '广州', 55000],
    ['赵六', 28, '深圳', 65000]
]
df2 = pd.DataFrame(data, columns=['姓名', '年龄', '城市', '工资'])

# 方法3：从 NumPy 数组
arr = np.array([
    ['张三', 25, '北京', 50000],
    ['李四', 30, '上海', 60000]
])
df3 = pd.DataFrame(arr, columns=['姓名', '年龄', '城市', '工资'])
df3[['年龄', '工资']] = df3[['年龄', '工资']].astype(int)

# 方法4：从文件读取（后面会详细讲）
```

## 📁 **3\. 数据读取与写入**

### **读取各种格式文件**

```python
# CSV 文件
df = pd.read_csv('data.csv')
df = pd.read_csv('data.csv', encoding='gbk')  # 中文编码
df = pd.read_csv('data.csv', sep=',')         # 分隔符
df = pd.read_csv('data.csv', header=0)        # 表头行
df = pd.read_csv('data.csv', index_col=0)     # 索引列
df = pd.read_csv('data.csv', usecols=['列1', '列2'])  # 选择列
df = pd.read_csv('data.csv', nrows=1000)      # 读取前1000行

# 处理大文件（分块读取）
chunk_size = 10000
chunks = []
for chunk in pd.read_csv('large_data.csv', chunksize=chunk_size):
    # 处理每个块
    processed_chunk = chunk[chunk['value'] > 0]
    chunks.append(processed_chunk)
df = pd.concat(chunks, ignore_index=True)

# Excel 文件
df = pd.read_excel('data.xlsx', sheet_name='Sheet1')
df = pd.read_excel('data.xlsx', sheet_name=0)      # 第一个工作表
df = pd.read_excel('data.xlsx', sheet_name=None)   # 读取所有工作表

# JSON 文件
df = pd.read_json('data.json')
df = pd.read_json('data.json', orient='records')   # 记录格式

# SQL 数据库
import sqlite3
conn = sqlite3.connect('database.db')
df = pd.read_sql('SELECT * FROM users', conn)
df = pd.read_sql_table('users', conn)              # 直接读取表
df = pd.read_sql_query('SELECT name, age FROM users WHERE age > 20', conn)

# 网页表格
url = 'https://example.com/table.html'
tables = pd.read_html(url)  # 返回 DataFrame 列表
df = tables[0]

# Parquet 文件（高效二进制格式）
df = pd.read_parquet('data.parquet')
```

### **写入文件**

```python
# CSV
df.to_csv('output.csv', index=False, encoding='utf-8-sig')  # 中文兼容
df.to_csv('output.csv', index=False, sep='|')               # 自定义分隔符

# Excel
with pd.ExcelWriter('output.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Sheet1', index=False)
    # 多个 DataFrame 写入不同工作表
    df_summary.to_excel(writer, sheet_name='Summary', index=False)

# JSON
df.to_json('output.json', orient='records', force_ascii=False)

# SQL
df.to_sql('table_name', conn, if_exists='replace', index=False)

# Parquet
df.to_parquet('output.parquet', compression='snappy')

# 多种格式同时保存
def save_dataframe(df, filename):
    """智能保存 DataFrame"""
    if filename.endswith('.csv'):
        df.to_csv(filename, index=False)
    elif filename.endswith('.xlsx'):
        df.to_excel(filename, index=False)
    elif filename.endswith('.json'):
        df.to_json(filename, orient='records')
    elif filename.endswith('.parquet'):
        df.to_parquet(filename)
    else:
        raise ValueError("不支持的格式")
```

## 🔍 **4\. 数据查看与基本信息**

### **查看数据**

```python
# 基本查看
print(df.head())           # 前5行
print(df.head(10))         # 前10行
print(df.tail())           # 后5行
print(df.sample(5))        # 随机5行
print(df.shape)            # (行数, 列数)
print(df.columns)          # 列名列表
print(df.index)            # 索引
print(df.dtypes)           # 每列数据类型

# 详细描述
print(df.info())           # 内存使用和数据类型
print(df.describe())       # 数值列统计
print(df.describe(include='all'))  # 所有列统计
print(df.describe(include=[np.number]))  # 只数值列
print(df.describe(include=[object]))     # 只对象列

# 唯一值和计数
print(df['城市'].unique())          # 唯一值数组
print(df['城市'].nunique())         # 唯一值数量
print(df['城市'].value_counts())    # 值计数
print(df['城市'].value_counts(normalize=True))  # 比例

# 缺失值统计
print(df.isnull().sum())            # 每列缺失值数量
print(df.isnull().sum().sum())      # 总缺失值数量
print(df.isnull().mean() * 100)     # 每列缺失值百分比
```

### **选择与索引**

```python
# 列选择
df['姓名']                    # 返回 Series
df[['姓名', '年龄']]           # 返回 DataFrame
df.loc[:, '姓名']             # 使用 loc
df.iloc[:, 0]                # 使用 iloc，第一列

# 行选择
df[0:3]                      # 前3行
df.iloc[0]                   # 第一行（Series）
df.iloc[[0, 2, 4]]           # 第1,3,5行
df.loc[df['年龄'] > 30]       # 条件选择

# 行和列同时选择
df.loc[df['年龄'] > 30, ['姓名', '城市']]
df.iloc[0:3, 1:3]

# 条件筛选
df[(df['年龄'] > 25) & (df['工资'] > 55000)]      # AND
df[(df['城市'] == '北京') | (df['城市'] == '上海')]  # OR
df[~df['姓名'].str.contains('张')]                 # NOT

# 基于字符串的选择
df[df['姓名'].str.startswith('张')]      # 以"张"开头
df[df['姓名'].str.contains('三|四')]     # 包含"三"或"四"
df[df['城市'].str.lower() == 'beijing']  # 忽略大小写

# Query 方法（SQL风格）
df.query('年龄 > 30 and 工资 > 50000')
df.query('城市 in ["北京", "上海"]')
df.query('姓名.str.contains("张")', engine='python')
```

## 🧹 **5\. 数据清洗与预处理**

### **处理缺失值**

```python
# 检测缺失值
df.isna()
df.notna()
df.isnull()   # isna 的别名

# 删除缺失值
df.dropna()                          # 删除任何包含 NA 的行
df.dropna(axis=1)                    # 删除任何包含 NA 的列
df.dropna(how='all')                 # 只删除全为 NA 的行
df.dropna(subset=['年龄', '工资'])     # 只在特定列检查
df.dropna(thresh=3)                  # 保留至少有3个非NA值的行

# 填充缺失值
df.fillna(0)                         # 填充为0
df.fillna(method='ffill')            # 向前填充
df.fillna(method='bfill')            # 向后填充
df.fillna(df.mean())                 # 用均值填充数值列
df.fillna(df.mode().iloc[0])         # 用众数填充
df['年龄'].fillna(df['年龄'].median(), inplace=True)  # 原地修改

# 插值
df.interpolate()                     # 线性插值
df.interpolate(method='time')        # 时间序列插值
df.interpolate(limit=2)              # 最多插值2个连续缺失值

# 高级缺失值处理
def handle_missing(df):
    """智能处理缺失值"""
    result = df.copy()
    
    # 数值列用中位数填充
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if result[col].isna().any():
            result[col] = result[col].fillna(result[col].median())
    
    # 分类列用众数填充
    cat_cols = result.select_dtypes(include=['object']).columns
    for col in cat_cols:
        if result[col].isna().any():
            mode_value = result[col].mode()[0] if not result[col].mode().empty else 'Unknown'
            result[col] = result[col].fillna(mode_value)
    
    return result
```

### **处理重复值**

```python
# 检测重复行
df.duplicated()                      # 标记重复行
df.duplicated(subset=['姓名', '城市']) # 基于特定列
df.duplicated(keep='first')          # 保留第一个（默认）
df.duplicated(keep='last')           # 保留最后一个
df.duplicated(keep=False)            # 标记所有重复

# 删除重复行
df.drop_duplicates()                 # 删除完全重复的行
df.drop_duplicates(subset=['姓名'])   # 基于姓名去重
df.drop_duplicates(keep='first')     # 保留第一个
df.drop_duplicates(keep='last')      # 保留最后一个
df.drop_duplicates(inplace=True)     # 原地修改

# 高级去重策略
def smart_deduplicate(df, key_columns):
    """智能去重：保留最新或最完整的数据"""
    # 按时间倒序排序（假设有 update_time 列）
    if 'update_time' in df.columns:
        df = df.sort_values('update_time', ascending=False)
    
    # 创建完整度评分
    df['completeness'] = df.notna().sum(axis=1) / df.shape[1]
    
    # 按关键列分组，选择最完整的数据
    deduplicated = df.sort_values('completeness', ascending=False)\
                    .drop_duplicates(subset=key_columns, keep='first')\
                    .drop(columns=['completeness'])
    
    return deduplicated
```

### **数据类型转换**

```python
# 查看数据类型
print(df.dtypes)

# 类型转换
df['年龄'] = df['年龄'].astype(int)
df['工资'] = pd.to_numeric(df['工资'], errors='coerce')
df['日期'] = pd.to_datetime(df['日期'])
df['日期'] = pd.to_datetime(df['日期'], format='%Y-%m-%d')  # 指定格式

# 分类数据
df['城市'] = df['城市'].astype('category')
df['城市_cat'] = pd.Categorical(df['城市'], categories=['北京', '上海', '广州', '深圳'], ordered=True)

# 布尔转换
df['高工资'] = df['工资'] > 55000
df['高工资'] = df['高工资'].astype(bool)

# 批量转换
def convert_types(df):
    """智能类型转换"""
    result = df.copy()
    
    # 尝试转换为数值类型
    for col in result.columns:
        # 跳过已经是数值或日期类型的列
        if result[col].dtype in [np.number, 'datetime64[ns]']:
            continue
        
        # 尝试转换为数值
        converted = pd.to_numeric(result[col], errors='ignore')
        if not converted is result[col]:
            result[col] = converted
        
        # 如果转换失败且看起来像日期
        elif result[col].dtype == 'object' and result[col].str.contains(r'\d{4}-\d{2}-\d{2}').any():
            try:
                result[col] = pd.to_datetime(result[col], errors='coerce')
            except:
                pass
    
    return result
```

## 📊 **6\. 数据处理与转换**

### **列操作**

```python
# 添加新列
df['年薪'] = df['工资'] * 12
df['年龄组'] = pd.cut(df['年龄'], bins=[0, 30, 40, 100], labels=['青年', '中年', '老年'])
df['工资级别'] = np.where(df['工资'] > 60000, '高', '低')

# 修改列名
df.rename(columns={'姓名': 'name', '年龄': 'age'}, inplace=True)
df.columns = ['Name', 'Age', 'City', 'Salary']  # 全部重命名
df.columns = df.columns.str.lower()            # 转为小写
df.columns = df.columns.str.replace(' ', '_')  # 替换空格

# 删除列
df.drop(columns=['年薪'], inplace=True)        # 删除指定列
df.drop(columns=df.columns[df.isna().mean() > 0.5], inplace=True)  # 删除缺失值多的列

# 列重排序
df = df[['城市', '姓名', '年龄', '工资']]        # 手动重排
df = df.reindex(sorted(df.columns), axis=1)    # 按字母排序

# 拆分列
df[['姓', '名']] = df['姓名'].str.split('', n=1, expand=True)

# 合并列
df['姓名_城市'] = df['姓名'] + '(' + df['城市'] + ')'
df['信息'] = df.apply(lambda row: f"{row['姓名']}-{row['年龄']}", axis=1)
```

### **行操作**

```python
# 添加行
new_row = pd.Series({'姓名': '钱七', '年龄': 40, '城市': '杭州', '工资': 70000})
df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# 批量添加
new_data = pd.DataFrame({
    '姓名': ['孙八', '周九'],
    '年龄': [45, 33],
    '城市': ['南京', '成都'],
    '工资': [72000, 58000]
})
df = pd.concat([df, new_data], ignore_index=True)

# 删除行
df.drop([0, 2], inplace=True)                  # 删除索引0和2
df.drop(df[df['年龄'] < 25].index, inplace=True)  # 条件删除

# 过滤行
df_filtered = df[df['工资'].between(50000, 60000)]  # 范围过滤
df_filtered = df[df['城市'].isin(['北京', '上海'])]  # 值列表过滤
```

### **数据转换**

```python
# 应用函数
df['工资_k'] = df['工资'].apply(lambda x: f"{x/1000:.1f}k")
df['姓名长度'] = df['姓名'].apply(len)
df[['年龄', '工资']] = df[['年龄', '工资']].applymap(lambda x: x * 1.1)  # 所有元素

# 向量化操作（更快）
df['工资_调整'] = df['工资'] * 1.1
df['年龄_平方'] = np.square(df['年龄'])

# 分组应用
def salary_category(x):
    if x < 50000:
        return '低'
    elif x < 60000:
        return '中'
    else:
        return '高'

df['薪资等级'] = df['工资'].apply(salary_category)

# 使用 pipe 链式操作
df_processed = (df
    .pipe(lambda d: d[d['年龄'] > 25])
    .pipe(lambda d: d.assign(工资=lambda x: x['工资'] * 1.1))
    .pipe(lambda d: d.sort_values('工资', ascending=False))
)
```

## 📈 **7\. 数据聚合与分组**

### **基础分组操作**

```python
# 单列分组
grouped = df.groupby('城市')
print(grouped.groups)  # 查看分组

# 多列分组
grouped = df.groupby(['城市', '薪资等级'])

# 分组统计
df.groupby('城市')['工资'].mean()           # 每个城市的平均工资
df.groupby('城市')['年龄'].agg(['mean', 'min', 'max', 'count'])
df.groupby('城市').agg({'工资': 'mean', '年龄': ['min', 'max']})

# 自定义聚合函数
def range_func(x):
    return x.max() - x.min()

df.groupby('城市').agg({
    '工资': ['mean', range_func],
    '年龄': lambda x: x.std()
})
```

### **高级分组操作**

```python
# 分组后过滤
# 保留平均工资大于55000的城市
df.groupby('城市').filter(lambda x: x['工资'].mean() > 55000)

# 分组后转换
# 计算每个城市相对于该城市平均工资的比值
df['相对工资'] = df.groupby('城市')['工资'].transform(lambda x: x / x.mean())

# 分组排名
df['城市内排名'] = df.groupby('城市')['工资'].rank(ascending=False, method='dense')

# 滚动/扩展窗口计算
df['工资_MA3'] = df.groupby('城市')['工资'].rolling(window=3).mean().reset_index(0, drop=True)
df['工资_累计'] = df.groupby('城市')['工资'].expanding().mean().reset_index(0, drop=True)

# 分组采样
sampled = df.groupby('城市', group_keys=False).apply(lambda x: x.sample(min(len(x), 2)))
```

### **透视表与交叉表**

```python
# 透视表（类似Excel数据透视表）
pivot = pd.pivot_table(df, 
                       values='工资', 
                       index='城市', 
                       columns='薪资等级', 
                       aggfunc='mean',
                       fill_value=0,
                       margins=True,  # 添加总计
                       margins_name='总计')

# 多层透视表
pivot_multi = pd.pivot_table(df,
                            values=['工资', '年龄'],
                            index=['城市', '薪资等级'],
                            aggfunc={'工资': 'mean', '年龄': ['min', 'max']})

# 交叉表（频数统计）
cross = pd.crosstab(df['城市'], df['薪资等级'], normalize='index')  # 行百分比
cross_multi = pd.crosstab([df['城市'], df['年龄组']], df['薪资等级'])
```

## 🔗 **8\. 数据合并与连接**

### **合并操作**

```python
# 创建示例数据
df1 = pd.DataFrame({
    'key': ['A', 'B', 'C', 'D'],
    'value1': [1, 2, 3, 4]
})

df2 = pd.DataFrame({
    'key': ['B', 'D', 'E', 'F'],
    'value2': [5, 6, 7, 8]
})

# 1. 内连接（交集）
inner = pd.merge(df1, df2, on='key', how='inner')

# 2. 左连接（左表全部）
left = pd.merge(df1, df2, on='key', how='left')

# 3. 右连接（右表全部）
right = pd.merge(df1, df2, on='key', how='right')

# 4. 外连接（并集）
outer = pd.merge(df1, df2, on='key', how='outer')

# 5. 基于多个键合并
df3 = pd.DataFrame({
    'key1': ['A', 'B', 'C'],
    'key2': ['X', 'Y', 'Z'],
    'value': [10, 20, 30]
})
multi = pd.merge(df1, df3, left_on='key', right_on='key1')

# 6. 连接指示器
merged = pd.merge(df1, df2, on='key', how='outer', indicator=True)
```

### **连接操作**

```python
# 纵向连接（堆叠）
df_top = df.head(2)
df_bottom = df.tail(2)
concatenated = pd.concat([df_top, df_bottom], axis=0)  # 纵向
concatenated = pd.concat([df_top, df_bottom], ignore_index=True)  # 重置索引

# 横向连接
df_left = df[['姓名', '年龄']]
df_right = df[['城市', '工资']]
combined = pd.concat([df_left, df_right], axis=1)

# 使用 join 方法
df1.set_index('key', inplace=True)
df2.set_index('key', inplace=True)
joined = df1.join(df2, how='inner')
```

### **复杂合并场景**

```python
# 合并多个DataFrame
from functools import reduce

dfs = [df1, df2, df3]
merged_all = reduce(lambda left, right: pd.merge(left, right, on='key', how='outer'), dfs)

# 合并时处理重复列名
df4 = pd.DataFrame({
    'key': ['A', 'B', 'C'],
    'value': [100, 200, 300]
})

merged_suffix = pd.merge(df1, df4, on='key', how='outer', suffixes=('_left', '_right'))

# 根据条件合并（类似SQL的WHERE JOIN）
# 需要先创建连接键或使用pandas的merge_asof
df5 = pd.DataFrame({
    'timestamp': pd.date_range('2023-01-01', periods=5, freq='H'),
    'value': [1, 2, 3, 4, 5]
})

df6 = pd.DataFrame({
    'timestamp': pd.date_range('2023-01-01 00:30:00', periods=5, freq='H'),
    'value2': [10, 20, 30, 40, 50]
})

# 最近时间合并
time_merged = pd.merge_asof(df5, df6, on='timestamp', direction='nearest')
```

## 📊 **9\. 时间序列处理**

### **时间数据处理**

```python
# 创建时间序列
dates = pd.date_range('2023-01-01', periods=10, freq='D')
ts = pd.Series(np.random.randn(10), index=dates)

# 时间索引操作
ts['2023-01-05']                          # 选择特定日期
ts['2023-01']                             # 选择整个一月
ts['2023-01-05':'2023-01-08']              # 选择范围

# 时间属性
ts.index.year                             # 年份
ts.index.month                            # 月份
ts.index.day                              # 日期
ts.index.dayofweek                        # 星期几（0=周一）
ts.index.quarter                          # 季度

# 时间重采样
daily_data = pd.Series(np.random.randn(30), 
                       index=pd.date_range('2023-01-01', periods=30, freq='D'))

monthly = daily_data.resample('M').mean()                  # 按月平均
weekly = daily_data.resample('W').sum()                    # 按周求和
business_days = daily_data.asfreq('B').fillna(method='ffill')  # 工作日频率

# 移动窗口计算
daily_data.rolling(window=7).mean()                       # 7天移动平均
daily_data.rolling(window=30, min_periods=1).mean()       # 30天移动平均
daily_data.expanding().mean()                             # 扩展窗口平均
```

### **时间序列分析**

```python
# 时间差计算
df['日期'] = pd.to_datetime(df['日期'])
df['天数差'] = (df['日期'] - df['日期'].min()).dt.days
df['月数差'] = (df['日期'].dt.year - df['日期'].min().year) * 12 + (df['日期'].dt.month - df['日期'].min().month)

# 周期分析
df['年份'] = df['日期'].dt.year
df['月份'] = df['日期'].dt.month
df['季度'] = df['日期'].dt.quarter
df['星期'] = df['日期'].dt.day_name()

# 时间序列分解
from statsmodels.tsa.seasonal import seasonal_decompose

result = seasonal_decompose(ts, model='additive', period=7)
result.plot()

# 时间序列特征工程
def create_time_features(df, date_col):
    """创建时间特征"""
    df = df.copy()
    df[f'{date_col}_year'] = df[date_col].dt.year
    df[f'{date_col}_month'] = df[date_col].dt.month
    df[f'{date_col}_day'] = df[date_col].dt.day
    df[f'{date_col}_dayofweek'] = df[date_col].dt.dayofweek
    df[f'{date_col}_quarter'] = df[date_col].dt.quarter
    df[f'{date_col}_is_weekend'] = df[date_col].dt.dayofweek.isin([5, 6]).astype(int)
    
    # 周期特征
    df[f'{date_col}_sin_month'] = np.sin(2 * np.pi * df[f'{date_col}_month']/12)
    df[f'{date_col}_cos_month'] = np.cos(2 * np.pi * df[f'{date_col}_month']/12)
    
    return df
```

## 📉 **10\. 数据可视化**

### **基础绘图**

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 设置样式
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette('husl')

# 1. 折线图
df.plot(x='日期', y='工资', kind='line', figsize=(10, 6))
plt.title('工资趋势图')
plt.xlabel('日期')
plt.ylabel('工资')
plt.show()

# 2. 柱状图
df['城市'].value_counts().plot(kind='bar', figsize=(10, 6))
plt.title('各城市人数分布')
plt.xlabel('城市')
plt.ylabel('人数')
plt.xticks(rotation=45)
plt.show()

# 3. 直方图
df['年龄'].plot(kind='hist', bins=10, figsize=(10, 6), alpha=0.7)
plt.title('年龄分布')
plt.xlabel('年龄')
plt.ylabel('频数')
plt.show()

# 4. 散点图
df.plot(kind='scatter', x='年龄', y='工资', figsize=(10, 6))
plt.title('年龄与工资关系')
plt.xlabel('年龄')
plt.ylabel('工资')
plt.show()

# 5. 箱线图
df.boxplot(column='工资', by='城市', figsize=(10, 6))
plt.title('各城市工资分布')
plt.suptitle('')  # 移除默认标题
plt.xlabel('城市')
plt.ylabel('工资')
plt.show()
```

### **高级可视化**

```python
# 子图
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

df['年龄'].plot(kind='hist', ax=axes[0, 0], title='年龄分布')
df['工资'].plot(kind='hist', ax=axes[0, 1], title='工资分布')
df.plot(kind='scatter', x='年龄', y='工资', ax=axes[1, 0], title='年龄vs工资')
df['城市'].value_counts().plot(kind='bar', ax=axes[1, 1], title='城市分布')

plt.tight_layout()
plt.show()

# 热力图
correlation = df[['年龄', '工资']].corr()
sns.heatmap(correlation, annot=True, cmap='coolwarm', center=0)
plt.title('相关性热力图')
plt.show()

# 成对关系图（Pairplot）
sns.pairplot(df[['年龄', '工资']])
plt.show()

# 分类散点图
sns.stripplot(x='城市', y='工资', data=df, jitter=True)
plt.title('各城市工资分布')
plt.xticks(rotation=45)
plt.show()

# 保存图表
fig = df.plot(x='日期', y='工资').get_figure()
fig.savefig('output.png', dpi=300, bbox_inches='tight')
```

## ⚡ **11\. 性能优化技巧**

### **高效数据处理**

```python
# 1. 使用向量化操作而不是循环
# 慢
for i in range(len(df)):
    df.loc[i, '新列'] = df.loc[i, '工资'] * 1.1

# 快
df['新列'] = df['工资'] * 1.1

# 2. 使用 .at 和 .iat 访问单个元素
# 慢
df.loc[0, '工资'] = 60000

# 快
df.at[0, '工资'] = 60000

# 3. 使用合适的数据类型
df['小整数'] = df['小整数'].astype(np.int8)
df['分类列'] = df['分类列'].astype('category')

# 4. 使用查询优化
# 创建索引
df_indexed = df.set_index('城市')
result = df_indexed.loc['北京']  # 快速查询

# 5. 使用 chunk 处理大数据
def process_large_file(filepath):
    chunk_size = 10000
    results = []
    
    for chunk in pd.read_csv(filepath, chunksize=chunk_size):
        # 处理每个chunk
        processed = chunk[chunk['value'] > 0]
        results.append(processed)
    
    return pd.concat(results, ignore_index=True)

# 6. 使用 eval() 进行表达式计算（大数据时）
df['结果'] = pd.eval('df.工资 * df.年龄 / 100')
```

### **内存优化**

```python
def reduce_memory_usage(df, verbose=True):
    """减少DataFrame内存使用"""
    numerics = ['int16', 'int32', 'int64', 'float16', 'float32', 'float64']
    start_mem = df.memory_usage().sum() / 1024**2
    
    for col in df.columns:
        col_type = df[col].dtypes
        
        if col_type in numerics:
            c_min = df[col].min()
            c_max = df[col].max()
            
            if str(col_type)[:3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                    df[col] = df[col].astype(np.int64)
            else:
                if c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                    df[col] = df[col].astype(np.float32)
                else:
                    df[col] = df[col].astype(np.float64)
        elif col_type == 'object':
            # 转换为category如果唯一值比例低
            num_unique_values = len(df[col].unique())
            num_total_values = len(df[col])
            if num_unique_values / num_total_values < 0.5:
                df[col] = df[col].astype('category')
    
    end_mem = df.memory_usage().sum() / 1024**2
    if verbose:
        print(f'内存使用从 {start_mem:.2f} MB 减少到 {end_mem:.2f} MB')
        print(f'减少了 {(100 * (start_mem - end_mem) / start_mem):.1f}%')
    
    return df
```

## 📋 **12\. 实战项目模板**

### **数据分析项目模板**

```python
"""
数据分析项目模板
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

class DataAnalysisProject:
    """数据分析项目模板类"""
    
    def __init__(self, data_path=None):
        self.data_path = data_path
        self.df = None
        self.report = {}
        
    def load_data(self, **kwargs):
        """加载数据"""
        print("📂 加载数据...")
        
        if self.data_path.endswith('.csv'):
            self.df = pd.read_csv(self.data_path, **kwargs)
        elif self.data_path.endswith('.xlsx'):
            self.df = pd.read_excel(self.data_path, **kwargs)
        elif self.data_path.endswith('.json'):
            self.df = pd.read_json(self.data_path, **kwargs)
        else:
            raise ValueError("不支持的格式")
        
        print(f"✅ 加载完成: {self.df.shape[0]} 行, {self.df.shape
```