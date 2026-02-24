# 📊 Matplotlib Pyplot 完全可视化教程

Matplotlib 是 Python 最流行的绘图库，而 `pyplot` 是其核心接口。以下是完整的可视化教程：

## 📦 **1\. 安装与基础设置**

### **安装**

```bash
# 安装 matplotlib
pip install matplotlib

# 完整数据科学套件
pip install matplotlib numpy pandas seaborn

# Jupyter 中显示图形
%matplotlib inline  # 在 Notebook 中显示
%matplotlib notebook  # 交互式图形
```

### **基础导入与设置**

**🔥🔥**plt.style.use设置样式会覆盖rcParams配置，所以需要提前设置

```python
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# 设置图形样式
plt.style.use('seaborn-v0_8-darkgrid')  # 使用内置样式
# 可用样式: 'default', 'classic', 'ggplot', 'seaborn', 'seaborn-darkgrid', etc.

# 设置中文字体（解决中文显示问题）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 设置图形尺寸和DPI
plt.rcParams['figure.figsize'] = (10, 6)  # 默认图形尺寸
plt.rcParams['figure.dpi'] = 100  # 分辨率
plt.rcParams['savefig.dpi'] = 300  # 保存分辨率

# 创建数据
x = np.linspace(0, 10, 100)
y = np.sin(x)
```

## 🎨 **2\. 基础图形绘制**

### **折线图 (Line Plot)**

**linestyle样式**

-   \- : 实线
    
-   \- - ：虚线
    
-   \-. ：虚实线
    
-   : ：点线
    

**marker样式**

-   o: 圆点
    
-   s: 方形
    
-   ^：三角形
    
-   D：菱形
    
-   \*：五角星
    

```python
# 基础折线图
plt.figure(figsize=(10, 6))  # 创建图形

plt.plot(x, y, 
         label='正弦波',      # 图例标签
         color='blue',        # 颜色
         linewidth=2,         # 线宽
         linestyle='-',       # 线型: '-', '--', '-.', ':'
         marker='o',          # 标记点: 'o', 's', '^', 'D', '*'
         markersize=5,        # 标记大小
         markeredgecolor='red', # 标记边框颜色
         markerfacecolor='yellow' # 标记填充颜色
        )

# 添加标题和标签
plt.title('正弦函数图像', fontsize=16, fontweight='bold')
plt.xlabel('X轴', fontsize=12)
plt.ylabel('Y轴', fontsize=12)

# 添加图例
plt.legend(loc='best', fontsize=10)

# 网格线
plt.grid(True, alpha=0.3, linestyle='--')

# 设置坐标轴范围
plt.xlim(0, 10)
plt.ylim(-1.5, 1.5)

# 设置刻度
plt.xticks(np.arange(0, 11, 1))
plt.yticks(np.arange(-1.5, 2, 0.5))

# 显示图形
plt.tight_layout()  # 自动调整布局
plt.show()

# 多线条折线图
plt.figure(figsize=(10, 6))

y1 = np.sin(x)
y2 = np.cos(x)
y3 = np.sin(x) * np.cos(x)

plt.plot(x, y1, label='sin(x)', linewidth=2)
plt.plot(x, y2, label='cos(x)', linewidth=2, linestyle='--')
plt.plot(x, y3, label='sin(x)*cos(x)', linewidth=2, linestyle=':')

plt.title('多个函数图像')
plt.xlabel('X')
plt.ylabel('Y')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

### **散点图 (Scatter Plot)**

```python
# 创建数据
np.random.seed(42)
x_scatter = np.random.randn(100)
y_scatter = x_scatter + np.random.randn(100) * 0.5

plt.figure(figsize=(10, 6))

# 基础散点图
plt.scatter(x_scatter, y_scatter, 
           alpha=0.6,           # 透明度
           c='blue',            # 颜色
           edgecolors='black',  # 边缘颜色
           linewidths=0.5,      # 边缘线宽
           s=50,                # 点的大小
           marker='o',          # 点形状
           label='数据点'
          )

plt.title('散点图示例', fontsize=14)
plt.xlabel('X值')
plt.ylabel('Y值')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()

# 气泡图（大小和颜色映射）
plt.figure(figsize=(10, 6))

# 创建气泡大小和颜色数据
size = np.random.randint(10, 300, 100)  # 气泡大小
colors = np.random.rand(100)           # 颜色值

# 使用颜色映射
scatter = plt.scatter(x_scatter, y_scatter, 
                      s=size,          # 大小数组
                      c=colors,        # 颜色数组
                      alpha=0.6,
                      cmap='viridis',  # 颜色映射
                      edgecolors='black',
                      linewidths=0.5
                     )

# 添加颜色条
plt.colorbar(scatter, label='颜色值')

plt.title('气泡图（大小和颜色表示不同维度）')
plt.xlabel('X轴')
plt.ylabel('Y轴')
plt.grid(True, alpha=0.3)
plt.show()
```

### **柱状图 (Bar Chart)**

```python
# 创建数据
categories = ['A', 'B', 'C', 'D', 'E']
values = [23, 45, 56, 78, 33]
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
errors = [2, 3, 4, 2, 3]  # 误差值

plt.figure(figsize=(10, 6))

# 垂直柱状图
bars = plt.bar(categories, values,
               color=colors,           # 颜色列表
               edgecolor='black',      # 边缘颜色
               linewidth=1.5,          # 边缘线宽
               alpha=0.8,              # 透明度
               yerr=errors,            # 误差线
               capsize=5,              # 误差线帽子大小
               label='数据'
              )

# 在柱子上添加数值标签
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 0.5,
             f'{height}', ha='center', va='bottom', fontsize=10)

plt.title('垂直柱状图', fontsize=14, fontweight='bold')
plt.xlabel('类别', fontsize=12)
plt.ylabel('值', fontsize=12)
plt.ylim(0, max(values) * 1.2)  # 设置Y轴范围
plt.legend()
plt.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.show()

# 水平柱状图
plt.figure(figsize=(10, 6))

bars_h = plt.barh(categories, values,
                  color=colors,
                  edgecolor='black',
                  linewidth=1.5,
                  alpha=0.8)

# 添加数值标签
for bar in bars_h:
    width = bar.get_width()
    plt.text(width + 1, bar.get_y() + bar.get_height()/2.,
             f'{width}', ha='left', va='center', fontsize=10)

plt.title('水平柱状图')
plt.xlabel('值')
plt.ylabel('类别')
plt.xlim(0, max(values) * 1.2)
plt.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.show()

# 分组柱状图
categories = ['Q1', 'Q2', 'Q3', 'Q4']
product_a = [23, 34, 25, 40]
product_b = [30, 28, 35, 30]
product_c = [25, 32, 28, 35]

x = np.arange(len(categories))
width = 0.25  # 柱宽

plt.figure(figsize=(10, 6))

plt.bar(x - width, product_a, width, label='产品A', color='#FF6B6B', alpha=0.8)
plt.bar(x, product_b, width, label='产品B', color='#4ECDC4', alpha=0.8)
plt.bar(x + width, product_c, width, label='产品C', color='#45B7D1', alpha=0.8)

plt.title('分组柱状图（季度销量）')
plt.xlabel('季度')
plt.ylabel('销量')
plt.xticks(x, categories)
plt.legend()
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()

# 堆叠柱状图
plt.figure(figsize=(10, 6))

plt.bar(categories, product_a, label='产品A', color='#FF6B6B', alpha=0.8)
plt.bar(categories, product_b, bottom=product_a, label='产品B', color='#4ECDC4', alpha=0.8)
plt.bar(categories, product_c, bottom=np.array(product_a)+np.array(product_b), 
        label='产品C', color='#45B7D1', alpha=0.8)

plt.title('堆叠柱状图（季度总销量）')
plt.xlabel('季度')
plt.ylabel('总销量')
plt.legend()
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()
```

### **直方图 (Histogram)**

```python
# 创建正态分布数据
np.random.seed(42)
data = np.random.normal(0, 1, 1000)
data2 = np.random.normal(2, 1.5, 800)

plt.figure(figsize=(12, 5))

# 子图1：基础直方图
plt.subplot(1, 2, 1)
plt.hist(data, 
         bins=30,                # 柱的数量或边界
         color='skyblue',        # 颜色
         edgecolor='black',      # 边缘颜色
         alpha=0.7,              # 透明度
         density=True,           # 显示密度而不是计数
         label='数据分布'
        )

# 添加理论正态分布曲线
from scipy.stats import norm
x = np.linspace(-4, 4, 100)
plt.plot(x, norm.pdf(x, 0, 1), 'r-', linewidth=2, label='理论分布')

plt.title('直方图（带密度曲线）')
plt.xlabel('值')
plt.ylabel('密度')
plt.legend()
plt.grid(alpha=0.3)

# 子图2：多个数据集的直方图
plt.subplot(1, 2, 2)
plt.hist([data, data2], 
         bins=30,
         color=['skyblue', 'lightcoral'],
         edgecolor='black',
         alpha=0.7,
         density=True,
         label=['数据集1', '数据集2'],
         stacked=True  # 堆叠显示
        )

plt.title('多数据集直方图')
plt.xlabel('值')
plt.ylabel('密度')
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.show()

# 累积直方图
plt.figure(figsize=(10, 6))

plt.hist(data, 
         bins=30,
         color='lightgreen',
         edgecolor='black',
         alpha=0.7,
         density=True,
         cumulative=True,  # 累积分布
         histtype='step',  # 线型
         linewidth=2,
         label='累积分布'
        )

plt.title('累积分布直方图')
plt.xlabel('值')
plt.ylabel('累积概率')
plt.legend()
plt.grid(alpha=0.3)
plt.show()
```

### **箱线图 (Box Plot)**

```python
# 创建数据
np.random.seed(42)
data_box = [np.random.normal(0, 1, 100),
            np.random.normal(2, 1.5, 100),
            np.random.normal(-1, 0.8, 100),
            np.random.normal(3, 2, 100)]

labels = ['组A', '组B', '组C', '组D']

plt.figure(figsize=(10, 6))

# 基础箱线图
bp = plt.boxplot(data_box,
                 labels=labels,
                 patch_artist=True,  # 填充颜色
                 notch=True,         # 显示凹口
                 showmeans=True,     # 显示均值
                 meanline=True,      # 均值线
                 showfliers=True     # 显示异常值
                )

# 自定义颜色
colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightsalmon']
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.6)

# 设置中位数线颜色
for median in bp['medians']:
    median.set(color='red', linewidth=2)

# 设置均值线
for mean in bp['means']:
    mean.set(color='green', linewidth=2, linestyle='--')

plt.title('箱线图（显示均值和中位数）')
plt.ylabel('数值')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()

# 小提琴图（增强版箱线图）
from matplotlib import cm

plt.figure(figsize=(10, 6))

# 使用 seaborn 更简单，这里用 matplotlib 实现
parts = plt.violinplot(data_box, showmeans=False, showmedians=True)

# 自定义颜色
for pc, color in zip(parts['bodies'], colors):
    pc.set_facecolor(color)
    pc.set_alpha(0.6)

plt.xticks(range(1, len(labels) + 1), labels)
plt.title('小提琴图')
plt.ylabel('数值')
plt.grid(axis='y', alpha=0.3)
plt.show()
```

### **饼图 (Pie Chart)**

```python
# 创建数据
sizes = [15, 30, 45, 10]
labels = ['苹果', '香蕉', '橙子', '其他']
colors = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99']
explode = (0, 0.1, 0, 0)  # 突出显示第二块

plt.figure(figsize=(8, 8))

# 基础饼图
wedges, texts, autotexts = plt.pie(sizes,
                                   explode=explode,
                                   labels=labels,
                                   colors=colors,
                                   autopct='%1.1f%%',  # 百分比格式
                                   shadow=True,        # 阴影
                                   startangle=90,      # 起始角度
                                   textprops={'fontsize': 12}
                                  )

# 自定义文本
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontsize(10)
    autotext.set_fontweight('bold')

plt.title('水果销售占比', fontsize=14, fontweight='bold')
plt.axis('equal')  # 保证是圆形
plt.legend(wedges, labels, title="水果种类", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
plt.tight_layout()
plt.show()

# 环形图
plt.figure(figsize=(8, 8))

# 内环
plt.pie(sizes, 
        colors=colors,
        startangle=90,
        wedgeprops=dict(width=0.3, edgecolor='w')
       )

# 外环
plt.pie([i*2 for i in sizes], 
        colors=colors,
        radius=0.7,
        startangle=90,
        wedgeprops=dict(width=0.3, edgecolor='w')
       )

plt.title('环形图示例')
plt.axis('equal')
plt.legend(labels, loc='upper right')
plt.tight_layout()
plt.show()
```

## 📈 **3\. 高级图形功能**

### **子图系统 (Subplots)**

```python
# 方法1：使用 plt.subplot()
plt.figure(figsize=(12, 8))

# 2x2 网格
plt.subplot(2, 2, 1)  # (行, 列, 位置)
x = np.linspace(0, 10, 100)
plt.plot(x, np.sin(x), 'b-')
plt.title('正弦函数')
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 2)
plt.plot(x, np.cos(x), 'r--')
plt.title('余弦函数')
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 3)
plt.scatter(np.random.randn(100), np.random.randn(100), alpha=0.6)
plt.title('随机散点图')
plt.grid(True, alpha=0.3)

plt.subplot(2, 2, 4)
categories = ['A', 'B', 'C', 'D']
values = [20, 35, 30, 15]
plt.bar(categories, values, color=['red', 'green', 'blue', 'yellow'])
plt.title('柱状图')
plt.grid(axis='y', alpha=0.3)

plt.suptitle('多子图示例', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.show()

# 方法2：使用 plt.subplots()（推荐）
fig, axes = plt.subplots(2, 3, figsize=(15, 10), sharex=False, sharey=False)

# 访问各个子图
axes[0, 0].plot(x, np.sin(x), 'b-')
axes[0, 0].set_title('正弦函数')
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].plot(x, np.cos(x), 'r--')
axes[0, 1].set_title('余弦函数')
axes[0, 1].grid(True, alpha=0.3)

axes[0, 2].scatter(np.random.randn(100), np.random.randn(100), alpha=0.6)
axes[0, 2].set_title('散点图')
axes[0, 2].grid(True, alpha=0.3)

axes[1, 0].bar(categories, values)
axes[1, 0].set_title('柱状图')
axes[1, 0].grid(axis='y', alpha=0.3)

axes[1, 1].hist(np.random.randn(1000), bins=30, alpha=0.7, edgecolor='black')
axes[1, 1].set_title('直方图')
axes[1, 1].grid(True, alpha=0.3)

axes[1, 2].pie(sizes, labels=labels, autopct='%1.1f%%')
axes[1, 2].set_title('饼图')

# 设置总标题
fig.suptitle('高级子图布局', fontsize=16, fontweight='bold', y=1.02)

plt.tight_layout()
plt.show()

# 复杂子图布局
fig = plt.figure(figsize=(12, 8))

# 使用 GridSpec 创建复杂布局
gs = fig.add_gridspec(3, 3)

# 占据第一行所有列
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(x, np.sin(x) * np.cos(x), 'g-')
ax1.set_title('第一行：完整宽度')
ax1.grid(True, alpha=0.3)

# 第二行第一列，占两行高
ax2 = fig.add_subplot(gs[1:, 0])
ax2.scatter(np.random.randn(50), np.random.randn(50), c='red', alpha=0.6)
ax2.set_title('第二列：两行高度')

# 第二行第二、三列
ax3 = fig.add_subplot(gs[1, 1])
ax3.bar(['A', 'B', 'C'], [10, 20, 15])
ax3.set_title('柱状图')

ax4 = fig.add_subplot(gs[1, 2])
ax4.hist(np.random.randn(500), bins=20, alpha=0.7, color='orange')
ax4.set_title('直方图')

# 第三行第二、三列
ax5 = fig.add_subplot(gs[2, 1:])
ax5.plot(x, np.tan(x), 'purple')
ax5.set_title('第三行：两列宽度')
ax5.grid(True, alpha=0.3)
ax5.set_ylim(-10, 10)

plt.suptitle('复杂网格布局示例', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.show()
```

### **双Y轴图形**

```python
# 创建数据
x = np.arange(0, 10, 0.1)
y1 = np.sin(x)
y2 = np.exp(x/3)

fig, ax1 = plt.subplots(figsize=(10, 6))

# 第一个Y轴
color1 = 'tab:blue'
ax1.set_xlabel('X轴')
ax1.set_ylabel('sin(x)', color=color1)
line1 = ax1.plot(x, y1, color=color1, linewidth=2, label='sin(x)')
ax1.tick_params(axis='y', labelcolor=color1)

# 第二个Y轴
ax2 = ax1.twinx()
color2 = 'tab:red'
ax2.set_ylabel('exp(x/3)', color=color2)
line2 = ax2.plot(x, y2, color=color2, linewidth=2, linestyle='--', label='exp(x/3)')
ax2.tick_params(axis='y', labelcolor=color2)

# 组合图例
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper left')

plt.title('双Y轴图形示例')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

### **3D 图形**

```python
from mpl_toolkits.mplot3d import Axes3D

# 创建数据
x = np.linspace(-5, 5, 100)
y = np.linspace(-5, 5, 100)
X, Y = np.meshgrid(x, y)
Z = np.sin(np.sqrt(X**2 + Y**2))

fig = plt.figure(figsize=(14, 10))

# 3D曲面图
ax1 = fig.add_subplot(221, projection='3d')
surf = ax1.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8)
ax1.set_title('3D曲面图')
ax1.set_xlabel('X轴')
ax1.set_ylabel('Y轴')
ax1.set_zlabel('Z轴')
fig.colorbar(surf, ax=ax1, shrink=0.5, aspect=5)

# 3D线框图
ax2 = fig.add_subplot(222, projection='3d')
ax2.plot_wireframe(X, Y, Z, color='blue', alpha=0.6)
ax2.set_title('3D线框图')
ax2.set_xlabel('X轴')
ax2.set_ylabel('Y轴')
ax2.set_zlabel('Z轴')

# 3D散点图
ax3 = fig.add_subplot(223, projection='3d')
np.random.seed(42)
n_points = 200
x_scatter = np.random.randn(n_points)
y_scatter = np.random.randn(n_points)
z_scatter = np.random.randn(n_points)
colors = np.random.rand(n_points)
sizes = 100 * np.random.rand(n_points)

scatter = ax3.scatter(x_scatter, y_scatter, z_scatter, 
                      c=colors, s=sizes, alpha=0.6, cmap='plasma')
ax3.set_title('3D散点图')
ax3.set_xlabel('X轴')
ax3.set_ylabel('Y轴')
ax3.set_zlabel('Z轴')

# 3D等高线图
ax4 = fig.add_subplot(224, projection='3d')
contour = ax4.contour3D(X, Y, Z, 50, cmap='coolwarm')
ax4.set_title('3D等高线图')
ax4.set_xlabel('X轴')
ax4.set_ylabel('Y轴')
ax4.set_zlabel('Z轴')

plt.suptitle('3D图形示例', fontsize=16, fontweight='bold')
plt.tight_layout()
plt.show()
```

### **极坐标图**

```python
# 创建数据
theta = np.linspace(0, 2*np.pi, 100)
r = 1 + 0.5 * np.sin(5*theta)

fig = plt.figure(figsize=(12, 6))

# 极坐标折线图
ax1 = fig.add_subplot(131, projection='polar')
ax1.plot(theta, r, 'b-', linewidth=2)
ax1.set_title('极坐标折线图', pad=20)
ax1.grid(True)

# 极坐标散点图
ax2 = fig.add_subplot(132, projection='polar')
ax2.scatter(theta, r, c=theta, s=50, cmap='hsv', alpha=0.7)
ax2.set_title('极坐标散点图', pad=20)
ax2.grid(True)

# 极坐标柱状图
ax3 = fig.add_subplot(133, projection='polar')
bars = ax3.bar(theta, r, width=0.1, alpha=0.7, color=plt.cm.viridis(r/2))
ax3.set_title('极坐标柱状图', pad=20)
ax3.grid(True)

plt.suptitle('极坐标图形示例', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()
```

### **热力图 (Heatmap)**

```python
# 创建数据
np.random.seed(42)
data = np.random.rand(10, 12)
rows = [f'Row_{i}' for i in range(1, 11)]
cols = [f'Col_{j}' for j in range(1, 13)]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# 基础热力图
im1 = ax1.imshow(data, cmap='viridis', aspect='auto')
ax1.set_title('基础热力图', fontsize=14)
ax1.set_xlabel('列')
ax1.set_ylabel('行')

# 设置刻度
ax1.set_xticks(np.arange(len(cols)))
ax1.set_yticks(np.arange(len(rows)))
ax1.set_xticklabels(cols, rotation=45, ha='right')
ax1.set_yticklabels(rows)

# 添加数值标签
for i in range(len(rows)):
    for j in range(len(cols)):
        text = ax1.text(j, i, f'{data[i, j]:.2f}',
                       ha="center", va="center", color="w", fontsize=8)

# 相关性热力图
np.random.seed(42)
corr_data = np.random.randn(100, 6)
corr_matrix = np.corrcoef(corr_data.T)

im2 = ax2.imshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1, aspect='auto')
ax2.set_title('相关性热力图', fontsize=14)
ax2.set_xlabel('变量')
ax2.set_ylabel('变量')

# 设置刻度
var_labels = [f'Var_{i}' for i in range(1, 7)]
ax2.set_xticks(np.arange(len(var_labels)))
ax2.set_yticks(np.arange(len(var_labels)))
ax2.set_xticklabels(var_labels, rotation=45, ha='right')
ax2.set_yticklabels(var_labels)

# 添加数值标签
for i in range(len(var_labels)):
    for j in range(len(var_labels)):
        text = ax2.text(j, i, f'{corr_matrix[i, j]:.2f}',
                       ha="center", va="center", 
                       color="white" if abs(corr_matrix[i, j]) > 0.5 else "black",
                       fontsize=9, fontweight='bold')

# 添加颜色条
plt.colorbar(im1, ax=ax1, shrink=0.8)
plt.colorbar(im2, ax=ax2, shrink=0.8)

plt.tight_layout()
plt.show()
```

### **等高线图 (Contour Plot)**

```python
# 创建数据
x = np.linspace(-3, 3, 100)
y = np.linspace(-3, 3, 100)
X, Y = np.meshgrid(x, y)
Z = np.sin(X) * np.cos(Y)  # 二维函数

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# 等高线图
contour = axes[0].contour(X, Y, Z, 20, cmap='RdGy')
axes[0].clabel(contour, inline=True, fontsize=8)
axes[0].set_title('等高线图')
axes[0].set_xlabel('X')
axes[0].set_ylabel('Y')
axes[0].grid(True, alpha=0.3)

# 填充等高线图
contourf = axes[1].contourf(X, Y, Z, 20, cmap='viridis')
axes[1].set_title('填充等高线图')
axes[1].set_xlabel('X')
axes[1].set_ylabel('Y')
axes[1].grid(True, alpha=0.3)
plt.colorbar(contourf, ax=axes[1], shrink=0.8)

# 等高线+填充组合
contour = axes[2].contour(X, Y, Z, 20, colors='black', linewidths=0.5)
contourf = axes[2].contourf(X, Y, Z, 20, cmap='coolwarm', alpha=0.7)
axes[2].clabel(contour, inline=True, fontsize=8)
axes[2].set_title('组合等高线图')
axes[2].set_xlabel('X')
axes[2].set_ylabel('Y')
axes[2].grid(True, alpha=0.3)
plt.colorbar(contourf, ax=axes[2], shrink=0.8)

plt.tight_layout()
plt.show()
```

## 🎭 **4\. 图形美化与自定义**

### **颜色和样式**

```python
# 内置颜色
colors = plt.cm.tab10(np.arange(0, 1, 0.1))  # tab10 调色板
colors = plt.cm.viridis(np.linspace(0, 1, 10))  # viridis 调色板

# 自定义颜色映射
from matplotlib.colors import LinearSegmentedColormap

# 创建自定义颜色映射
colors_custom = ['#FF6B6B', '#FFE66D', '#4ECDC4', '#1A535C']
cmap_custom = LinearSegmentedColormap.from_list('custom', colors_custom)

# 使用示例
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# 内置调色板示例
colormaps = ['viridis', 'plasma', 'coolwarm', 'RdYlBu']
for ax, cmap_name in zip(axes.flat, colormaps):
    data = np.random.rand(10, 10)
    im = ax.imshow(data, cmap=cmap_name)
    ax.set_title(cmap_name)
    plt.colorbar(im, ax=ax, shrink=0.8)

plt.suptitle('不同颜色映射示例', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()

# 线型和标记样式
fig, ax = plt.subplots(figsize=(12, 6))

# 线型
linestyles = ['-', '--', '-.', ':']
for i, ls in enumerate(linestyles):
    ax.plot([i, i+1], [0, 1], ls=ls, linewidth=2, label=f'线型: {ls}')

# 标记
markers = ['o', 's', '^', 'D', '*', '+', 'x']
x_pos = np.arange(len(markers)) + 3
for i, marker in enumerate(markers):
    ax.scatter(x_pos[i], 0.5, s=100, marker=marker, label=f'标记: {marker}')

ax.set_xlim(-1, len(markers)+3)
ax.set_ylim(-0.5, 1.5)
ax.set_title('线型和标记样式')
ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

### **文本和标注**

```python
fig, ax = plt.subplots(figsize=(12, 8))

# 绘制一些数据
x = np.linspace(0, 10, 100)
y = np.sin(x)
ax.plot(x, y, 'b-', linewidth=2, label='sin(x)')

# 1. 基本文本
ax.text(5, 0.5, '这是文本', fontsize=12, color='red',
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

# 2. 带箭头的标注
ax.annotate('最大值', xy=(np.pi/2, 1), xytext=(3, 1.5),
            arrowprops=dict(arrowstyle='->', connectionstyle='arc3', color='green', linewidth=2),
            fontsize=12, color='green',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

# 3. 数学公式（LaTeX）
ax.text(7, -0.5, r'$f(x) = \sin(x)$', fontsize=14, color='purple',
        bbox=dict(boxstyle='round', facecolor='lavender', alpha=0.5))

# 4. 带边框的文本
ax.text(2, -0.7, '带边框文本', fontsize=12, color='blue',
        bbox=dict(boxstyle='round,pad=0.5', edgecolor='blue', facecolor='lightblue'))

# 5. 旋转文本
ax.text(8, 0, '旋转45度', fontsize=12, color='orange', rotation=45,
        bbox=dict(boxstyle='round', facecolor='peachpuff', alpha=0.5))

# 6. 多行文本
ax.text(0.5, -0.8, '这是第一行\n这是第二行\n这是第三行', 
        fontsize=10, color='brown',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# 设置图形
ax.set_title('文本和标注示例', fontsize=16, fontweight='bold')
ax.set_xlabel('X轴', fontsize=12)
ax.set_ylabel('Y轴', fontsize=12)
ax.legend()
ax.grid(True, alpha=0.3)
ax.set_xlim(0, 10)
ax.set_ylim(-1.5, 1.5)

plt.tight_layout()
plt.show()
```

### **图例高级设置**

```python
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
```