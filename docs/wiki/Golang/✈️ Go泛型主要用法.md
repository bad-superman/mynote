Go 语言在 1.18 版本正式引入了泛型。以下是 Go 泛型的主要用法：

## 1\. 基本语法

### 类型参数

```go
// 泛型函数
func Print[T any](value T) {
    fmt.Println(value)
}

// 使用
Print[int](42)
Print("hello")  // 类型推断
```

## 2\. 类型约束

### 使用接口作为约束

```go
// 定义约束
type Number interface {
    int | int64 | float32 | float64
}

// 使用约束
func Add[T Number](a, b T) T {
    return a + b
}

// 也可以使用预定义约束
func Max[T constraints.Ordered](a, b T) T {
    if a > b {
        return a
    }
    return b
}
```

## 3\. 泛型类型

### 泛型结构体

```go
// 栈的实现
type Stack[T any] struct {
    items []T
}

func (s *Stack[T]) Push(item T) {
    s.items = append(s.items, item)
}

func (s *Stack[T]) Pop() T {
    if len(s.items) == 0 {
        var zero T
        return zero
    }
    item := s.items[len(s.items)-1]
    s.items = s.items[:len(s.items)-1]
    return item
}

// 使用
var stack Stack[int]
stack.Push(10)
val := stack.Pop()
```

## 4\. 常用的内置约束

```go
import "golang.org/x/exp/constraints"

// constraints 包提供了常用约束
func Min[T constraints.Ordered](a, b T) T {
    if a < b {
        return a
    }
    return b
}

// comparable 约束（可用于 == 和 != 操作）
func Contains[T comparable](slice []T, target T) bool {
    for _, v := range slice {
        if v == target {
            return true
        }
    }
    return false
}
```

## 5\. 方法约束

```go
// 接口约束可以包含方法
type Stringer interface {
    String() string
}

func PrintString[T Stringer](value T) {
    fmt.Println(value.String())
}
```

## 6\. ~ 符号（底层类型约束）

```go
type MyInt int

type Int interface {
    ~int | ~int32 | ~int64  // ~ 表示包括底层类型为 int 的类型
}

func Process[T Int](value T) {
    // 可以接受 MyInt 类型
}
```

## 7\. 多个类型参数

```go
// 多个类型参数
func Pair[K comparable, V any](key K, value V) map[K]V {
    return map[K]V{key: value}
}

// 使用
result := Pair[string, int]("age", 25)
```

## 8\. 实际应用示例

### 数据处理

```go
// 过滤切片
func Filter[T any](slice []T, predicate func(T) bool) []T {
    var result []T
    for _, v := range slice {
        if predicate(v) {
            result = append(result, v)
        }
    }
    return result
}

// 使用
numbers := []int{1, 2, 3, 4, 5}
even := Filter(numbers, func(n int) bool {
    return n%2 == 0
})
```

### 泛型容器

```go
// 泛型链表节点
type Node[T any] struct {
    Value T
    Next  *Node[T]
}

// 队列
type Queue[T any] struct {
    head, tail *Node[T]
}

func (q *Queue[T]) Enqueue(value T) {
    node := &Node[T]{Value: value}
    if q.tail == nil {
        q.head = node
        q.tail = node
    } else {
        q.tail.Next = node
        q.tail = node
    }
}
```

## 9\. 注意事项

1.  **性能**：Go 泛型在编译时进行单态化，性能接近手动实现的类型特定版本
    
2.  **限制**：
    
    -   不能有泛型方法（只能有泛型类型的方法）
        
    -   类型参数不能用于方法接收器
        
    -   不能声明新的类型参数作为方法参数
        

## 10\. 实用技巧

```go
// 类型推断简化调用
func ConvertSlice[T1, T2 any](slice []T1, converter func(T1) T2) []T2 {
    result := make([]T2, len(slice))
    for i, v := range slice {
        result[i] = converter(v)
    }
    return result
}

// 组合约束
type Numeric interface {
    constraints.Integer | constraints.Float
}

func Sum[T Numeric](slice []T) T {
    var sum T
    for _, v := range slice {
        sum += v
    }
    return sum
}
```