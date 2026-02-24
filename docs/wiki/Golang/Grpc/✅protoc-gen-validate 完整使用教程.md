✅

✅

✅

# ✅protoc-gen-validate 完整使用教程

## **一、简介**

protoc-gen-validate 是谷歌官方推荐的 Protocol Buffers 验证插件，可以在 proto 文件中定义验证规则，自动生成验证代码。

## **二、安装**

### **1\. 安装依赖**

```bash
# 1. 安装 protoc
# macOS
brew install protobuf

# Ubuntu/Debian
sudo apt-get install protobuf-compiler

# 2. 安装 Go 插件
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# 3. 安装 protoc-gen-validate
go install github.com/envoyproxy/protoc-gen-validate@latest

# 验证安装
protoc-gen-validate --version
```

### **2\. 导入 validate.proto**

```bash
# 获取 validate.proto 文件
mkdir -p validate
cd validate
wget https://raw.githubusercontent.com/envoyproxy/protoc-gen-validate/main/validate/validate.proto

# 查看安装位置
go list -m -f '{{.Dir}}' github.com/envoyproxy/protoc-gen-validate
```

## **三、基本使用**

### **1\. 创建 proto 文件**

```protobuf
// user.proto
syntax = "proto3";

package example;

import "validate/validate.proto";

option go_package = "github.com/yourname/project/gen/go;example";

message User {
  uint64 id = 1 [
    (validate.rules).uint64.gt = 0  // 必须大于0
  ];
  
  string username = 2 [
    (validate.rules).string = {
      min_len: 3,
      max_len: 20,
      pattern: "^[a-zA-Z0-9_]+$"  // 只能包含字母数字下划线
    }
  ];
  
  string email = 3 [
    (validate.rules).string.email = true  // 必须为邮箱格式
  ];
  
  int32 age = 4 [
    (validate.rules).int32 = {
      gte: 18,
      lte: 100
    }
  ];
  
  repeated string tags = 5 [
    (validate.rules).repeated = {
      min_items: 1,
      max_items: 10,
      items: {
        string: {
          min_len: 1,
          max_len: 20
        }
      }
    }
  ];
  
  UserType type = 6 [
    (validate.rules).enum = {
      defined_only: true,
      not_in: [0]  // 不允许 UNKNOWN 类型
    }
  ];
  
  map<string, string> metadata = 7 [
    (validate.rules).map = {
      min_pairs: 0,
      max_pairs: 10,
      keys: {
        string: {
          pattern: "^[a-z_]+$"
        }
      },
      values: {
        string: {
          max_len: 100
        }
      }
    }
  ];
  
  oneof contact {
    string phone = 8 [
      (validate.rules).string = {
        pattern: "^1[3-9]\\d{9}$"  // 中国手机号格式
      }
    ];
    string wechat = 9 [
      (validate.rules).string = {
        min_len: 3,
        max_len: 20
      }
    ];
  }
}

enum UserType {
  USER_TYPE_UNKNOWN = 0;
  USER_TYPE_NORMAL = 1;
  USER_TYPE_VIP = 2;
  USER_TYPE_ADMIN = 3;
}

message CreateUserRequest {
  User user = 1 [
    (validate.rules).message.required = true
  ];
  
  string password = 2 [
    (validate.rules).string = {
      min_len: 8,
      max_len: 32,
      contains_any: "!@#$%^&*"  // 必须包含特殊字符
    }
  ];
}

message CreateUserResponse {
  uint64 user_id = 1;
}
```

### **2\. 生成代码**

```bash
#!/bin/bash
# generate.sh

# 设置路径
PROTO_DIR="./proto"
GEN_DIR="./gen/go"
VALIDATE_PATH="$(go list -m -f '{{.Dir}}' github.com/envoyproxy/protoc-gen-validate)/validate"

# 创建目录
mkdir -p ${GEN_DIR}

# 生成代码
protoc \
  --proto_path=${PROTO_DIR} \
  --proto_path=. \
  --proto_path=${VALIDATE_PATH} \
  --go_out=${GEN_DIR} \
  --go-grpc_out=${GEN_DIR} \
  --validate_out="lang=go:${GEN_DIR}" \
  ${PROTO_DIR}/*.proto

echo "代码生成完成！"
```

## **四、所有验证规则详解**

### **1\. 数值类型验证**

```protobuf
message NumberValidation {
  // int32/int64
  int32 int_field = 1 [
    (validate.rules).int32 = {
      const: 100,        // 必须等于100
      lt: 100,           // 小于100
      lte: 100,          // 小于等于100
      gt: 0,             // 大于0
      gte: 1,            // 大于等于1
      in: [1, 2, 3],     // 必须在列表中
      not_in: [0, 99]    // 不能在列表中
    }
  ];
  
  // uint32/uint64
  uint64 uint_field = 2 [
    (validate.rules).uint64 = {
      gt: 0,
      lt: 1000
    }
  ];
  
  // sint32/sint64（有符号整数）
  sint32 sint_field = 3 [
    (validate.rules).sint32 = {
      gte: -100,
      lte: 100
    }
  ];
  
  // fixed32/fixed64（固定长度）
  fixed32 fixed_field = 4 [
    (validate.rules).fixed32 = {
      gt: 0
    }
  ];
  
  // float/double
  double double_field = 5 [
    (validate.rules).double = {
      gt: 0.0,
      lt: 100.0,
      epsilon: 0.0001  // 浮点数精度
    }
  ];
}
```

### **2\. 字符串验证**

```protobuf
message StringValidation {
  string field = 1 [
    (validate.rules).string = {
      // 长度约束
      min_len: 3,
      max_len: 100,
      len: 10,           // 必须正好10个字符
      
      // 格式约束
      email: true,       // 邮箱格式
      hostname: true,    // 主机名格式
      ip: true,          // IP地址（v4或v6）
      ipv4: true,        // IPv4地址
      ipv6: true,        // IPv6地址
      uri: true,         // URI格式
      uri_ref: true,     // URI引用格式
      address: true,     // 地址格式（hostname:port）
      uuid: true,        // UUID格式
      
      // 内容约束
      pattern: "^[a-zA-Z0-9_]+$",  // 正则表达式
      contains: "abc",   // 必须包含子串
      not_contains: "123",  // 不能包含子串
      prefix: "user_",   // 必须以指定前缀开头
      suffix: "_id",     // 必须以指定后缀结尾
      
      // 字符集约束
      contains_any: "!@#$%",  // 必须包含任意指定字符
      not_contains_any: " \t\n",  // 不能包含任意指定字符
      
      // 其他
      ignore_empty: true,  // 空字符串时跳过验证
    }
  ];
}
```

### **3\. 布尔值验证**

```protobuf
message BoolValidation {
  bool field = 1 [
    (validate.rules).bool.const = true  // 必须为true
  ];
}
```

### **4\. 枚举验证**

```protobuf
enum Status {
  STATUS_UNKNOWN = 0;
  STATUS_ACTIVE = 1;
  STATUS_INACTIVE = 2;
  STATUS_DELETED = 3;
}

message EnumValidation {
  Status status = 1 [
    (validate.rules).enum = {
      defined_only: true,   // 必须是已定义的值
      in: [1, 2],           // 必须在列表中
      not_in: [0, 3]        // 不能在列表中
    }
  ];
}
```

### **5\. 消息验证**

```protobuf
message MessageValidation {
  // 必须存在
  User user = 1 [
    (validate.rules).message.required = true
  ];
  
  // 可选但存在时必须验证
  Profile profile = 2 [
    (validate.rules).message.required = false  // 默认就是false
  ];
  
  // 跳过验证
  Config config = 3 [
    (validate.rules).message.skip = true
  ];
}
```

### **6\. 数组验证**

```protobuf
message RepeatedValidation {
  repeated string items = 1 [
    (validate.rules).repeated = {
      min_items: 1,
      max_items: 10,
      unique: true,  // 元素必须唯一
      items: {
        string: {
          min_len: 1,
          max_len: 50
        }
      }
    }
  ];
  
  // 嵌套数组
  repeated repeated int32 matrix = 2 [
    (validate.rules).repeated = {
      min_items: 1,
      items: {
        repeated: {
          min_items: 3,
          max_items: 3,
          items: {
            int32: {
              gte: 0
            }
          }
        }
      }
    }
  ];
}
```

### **7\. Map验证**

```protobuf
message MapValidation {
  map<string, string> config = 1 [
    (validate.rules).map = {
      min_pairs: 1,
      max_pairs: 10,
      no_sparse: true,  // 不允许有空值
      keys: {
        string: {
          pattern: "^[a-z_]+$"
        }
      },
      values: {
        string: {
          max_len: 100
        }
      }
    }
  ];
  
  map<int32, User> users = 2 [
    (validate.rules).map = {
      min_pairs: 0,
      values: {
        message: {
          required: true,
          skip: false
        }
      }
    }
  ];
}
```

### **8\. OneOf验证**

```protobuf
message OneOfValidation {
  oneof contact_method {
    option (validate.required) = true;  // 必须选择其中一个
    
    string email = 1 [
      (validate.rules).string.email = true
    ];
    
    string phone = 2 [
      (validate.rules).string = {
        pattern: "^1[3-9]\\d{9}$"
      }
    ];
    
    Address address = 3 [
      (validate.rules).message.required = true
    ];
  }
}
```

### **9\. 时间戳验证**

```protobuf
import "google/protobuf/timestamp.proto";

message TimestampValidation {
  google.protobuf.Timestamp created_at = 1 [
    (validate.rules).timestamp = {
      required: true,
      gt: {seconds: 1609459200},  // 大于2021-01-01
      within: {seconds: 31536000} // 在一年内（从当前时间）
    }
  ];
  
  google.protobuf.Timestamp expires_at = 2 [
    (validate.rules).timestamp = {
      gt_now: true,      // 必须大于当前时间
      within: {seconds: 2592000}  // 30天内
    }
  ];
}
```

### **10\. Duration验证**

```protobuf
import "google/protobuf/duration.proto";

message DurationValidation {
  google.protobuf.Duration timeout = 1 [
    (validate.rules).duration = {
      required: true,
      gt: {seconds: 1},      // 大于1秒
      lt: {seconds: 300},    // 小于5分钟
      within: {seconds: 60}  // 在60秒范围内
    }
  ];
}
```

## **五、自定义验证规则**

### **1\. 自定义消息级别验证**

```protobuf
message Transaction {
  double amount = 1;
  string currency = 2;
  
  // 自定义验证（需要在生成代码后实现）
  option (validate.disabled) = false;
}

// 然后在Go代码中实现自定义验证
```

### **2\. 条件验证**

```protobuf
message ConditionalValidation {
  string type = 1;
  string value = 2 [
    (validate.rules).string = {
      min_len: 1,
      max_len: 100
    }
  ];
  
  // 自定义规则：如果type为"email"，则value必须是邮箱
  // 这需要在业务代码中实现
}
```

## **六、Go代码中使用**

### **1\. 基础验证**

```go
package main

import (
    "fmt"
    "log"
    
    "github.com/envoyproxy/protoc-gen-validate/validate"
)

func main() {
    // 创建用户
    user := &example.User{
        Id:       1001,
        Username: "john_doe",
        Email:    "john@example.com",
        Age:      25,
        Tags:     []string{"golang", "backend"},
        Type:     example.UserType_USER_TYPE_NORMAL,
    }
    
    // 验证
    if err := user.Validate(); err != nil {
        if verr, ok := err.(validate.Error); ok {
            fmt.Printf("验证失败: 字段=%s, 原因=%v\n", verr.Field, verr.Reason)
        } else {
            log.Fatalf("验证失败: %v", err)
        }
        return
    }
    
    fmt.Println("验证通过!")
}
```

### **2\. gRPC拦截器集成**

```go
package main

import (
    "context"
    "fmt"
    
    "github.com/envoyproxy/protoc-gen-validate/validate"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

// ValidationInterceptor 验证拦截器
func ValidationInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        // 检查是否实现了Validate方法
        if v, ok := req.(interface{ Validate() error }); ok {
            if err := v.Validate(); err != nil {
                // 转换为友好的错误信息
                errMsg := formatValidationError(err)
                return nil, status.Errorf(codes.InvalidArgument, "参数验证失败: %s", errMsg)
            }
        }
        
        return handler(ctx, req)
    }
}

// 格式化验证错误
func formatValidationError(err error) string {
    if verr, ok := err.(validate.Error); ok {
        // 根据错误类型返回友好信息
        switch verr.Reason {
        case validate.Error_REQUIRED:
            return fmt.Sprintf("字段 %s 不能为空", verr.Field)
        case validate.Error_TOO_SHORT:
            return fmt.Sprintf("字段 %s 长度太短", verr.Field)
        case validate.Error_TOO_LONG:
            return fmt.Sprintf("字段 %s 长度太长", verr.Field)
        case validate.Error_PATTERN_MISMATCH:
            return fmt.Sprintf("字段 %s 格式不正确", verr.Field)
        default:
            return verr.Error()
        }
    }
    
    // 处理多个错误
    if multiErr, ok := err.(validate.Errors); ok {
        var msgs []string
        for _, e := range multiErr {
            msgs = append(msgs, formatValidationError(e))
        }
        return fmt.Sprintf("多个验证错误: %v", msgs)
    }
    
    return err.Error()
}

// 使用拦截器
func main() {
    server := grpc.NewServer(
        grpc.UnaryInterceptor(ValidationInterceptor()),
    )
    
    // 注册服务...
}
```

### **3\. 自定义验证扩展**

```go
package main

import (
    "context"
    "regexp"
    
    "github.com/go-playground/validator/v10"
    "google.golang.org/grpc"
)

// 扩展验证器
type CustomValidator struct {
    validator *validator.Validate
}

func NewCustomValidator() *CustomValidator {
    v := validator.New()
    
    // 注册自定义验证规则
    v.RegisterValidation("chinese_mobile", func(fl validator.FieldLevel) bool {
        mobile := fl.Field().String()
        re := regexp.MustCompile(`^1[3-9]\d{9}$`)
        return re.MatchString(mobile)
    })
    
    v.RegisterValidation("strong_password", func(fl validator.FieldLevel) bool {
        password := fl.Field().String()
        if len(password) < 8 {
            return false
        }
        
        hasUpper := regexp.MustCompile(`[A-Z]`).MatchString(password)
        hasLower := regexp.MustCompile(`[a-z]`).MatchString(password)
        hasNumber := regexp.MustCompile(`[0-9]`).MatchString(password)
        hasSpecial := regexp.MustCompile(`[!@#$%^&*]`).MatchString(password)
        
        return hasUpper && hasLower && hasNumber && hasSpecial
    })
    
    return &CustomValidator{validator: v}
}

// 集成到gRPC拦截器
func (cv *CustomValidator) Interceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        // 先使用protoc-gen-validate验证
        if v, ok := req.(interface{ Validate() error }); ok {
            if err := v.Validate(); err != nil {
                return nil, status.Errorf(codes.InvalidArgument, "基础验证失败: %v", err)
            }
        }
        
        // 再使用自定义验证器
        if err := cv.validator.Struct(req); err != nil {
            return nil, status.Errorf(codes.InvalidArgument, "自定义验证失败: %v", err)
        }
        
        return handler(ctx, req)
    }
}
```

## **七、高级功能**

### **1\. 错误信息国际化**

```go
package i18n

import (
    "github.com/envoyproxy/protoc-gen-validate/validate"
)

// 国际化错误信息
var errorMessages = map[validate.Error_Reason]map[string]string{
    validate.Error_REQUIRED: {
        "en": "field is required",
        "zh": "字段不能为空",
        "ja": "フィールドは必須です",
    },
    validate.Error_TOO_SHORT: {
        "en": "field is too short",
        "zh": "字段长度太短",
        "ja": "フィールドが短すぎます",
    },
    // ... 其他错误类型
}

func TranslateError(err error, lang string) string {
    if verr, ok := err.(validate.Error); ok {
        if msgs, ok := errorMessages[verr.Reason]; ok {
            if msg, ok := msgs[lang]; ok {
                return msg
            }
        }
    }
    return err.Error()
}
```

### **2\. 性能优化**

```go
package validation

import (
    "sync"
    
    "github.com/envoyproxy/protoc-gen-validate/validate"
)

// 验证器缓存
var validatorPool = sync.Pool{
    New: func() interface{} {
        return &validate.Validator{}
    },
}

func GetValidator() *validate.Validator {
    return validatorPool.Get().(*validate.Validator)
}

func PutValidator(v *validate.Validator) {
    validatorPool.Put(v)
}

// 带缓存的验证
func ValidateWithCache(msg interface{ Validate() error }) error {
    // 直接使用Validate方法（内部有缓存机制）
    return msg.Validate()
}
```

### **3\. 验证规则动态加载**

```go
package config

import (
    "encoding/json"
    "os"
)

// 从配置文件加载验证规则
type ValidationRules struct {
    MinUsernameLength int    `json:"min_username_length"`
    MaxUsernameLength int    `json:"max_username_length"`
    MinPasswordLength int    `json:"min_password_length"`
    AllowedCountries  []string `json:"allowed_countries"`
}

func LoadValidationRules(filePath string) (*ValidationRules, error) {
    data, err := os.ReadFile(filePath)
    if err != nil {
        return nil, err
    }
    
    var rules ValidationRules
    if err := json.Unmarshal(data, &rules); err != nil {
        return nil, err
    }
    
    return &rules, nil
}
```

## **八、测试验证规则**

### **1\. 单元测试**

```go
package test

import (
    "testing"
    
    "github.com/stretchr/testify/assert"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    
    pb "github.com/yourname/project/gen/go"
)

func TestUserValidation(t *testing.T) {
    tests := []struct {
        name    string
        user    *pb.User
        wantErr bool
    }{
        {
            name: "有效用户",
            user: &pb.User{
                Id:       1001,
                Username: "john_doe",
                Email:    "john@example.com",
                Age:      25,
                Type:     pb.UserType_USER_TYPE_NORMAL,
            },
            wantErr: false,
        },
        {
            name: "用户名太短",
            user: &pb.User{
                Id:       1002,
                Username: "jo",  // 少于3个字符
                Email:    "john@example.com",
                Age:      25,
            },
            wantErr: true,
        },
        {
            name: "邮箱格式错误",
            user: &pb.User{
                Id:       1003,
                Username: "jane_doe",
                Email:    "invalid-email",  // 无效邮箱
                Age:      30,
            },
            wantErr: true,
        },
        {
            name: "年龄太小",
            user: &pb.User{
                Id:       1004,
                Username: "teen_user",
                Email:    "teen@example.com",
                Age:      16,  // 小于18
            },
            wantErr: true,
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := tt.user.Validate()
            
            if tt.wantErr {
                assert.Error(t, err)
                // 验证错误类型
                if s, ok := status.FromError(err); ok {
                    assert.Equal(t, codes.InvalidArgument, s.Code())
                }
            } else {
                assert.NoError(t, err)
            }
        })
    }
}

// 测试gRPC拦截器
func TestValidationInterceptor(t *testing.T) {
    interceptor := ValidationInterceptor()
    
    handler := func(ctx context.Context, req interface{}) (interface{}, error) {
        return "success", nil
    }
    
    // 测试有效请求
    validUser := &pb.CreateUserRequest{
        User: &pb.User{
            Id:       1001,
            Username: "test_user",
            Email:    "test@example.com",
            Age:      25,
        },
        Password: "Password123!",
    }
    
    resp, err := interceptor(
        context.Background(),
        validUser,
        &grpc.UnaryServerInfo{
            FullMethod: "/example.UserService/CreateUser",
        },
        handler,
    )
    
    assert.NoError(t, err)
    assert.Equal(t, "success", resp)
}
```

### **2\. 性能测试**

```go
package benchmark

import (
    "testing"
    
    pb "github.com/yourname/project/gen/go"
)

func BenchmarkUserValidation(b *testing.B) {
    user := &pb.User{
        Id:       1001,
        Username: "benchmark_user",
        Email:    "benchmark@example.com",
        Age:      30,
        Tags:     []string{"test", "benchmark"},
        Type:     pb.UserType_USER_TYPE_VIP,
    }
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _ = user.Validate()
    }
}
```

## **九、最佳实践**

### **1\. 项目结构**

```text
project/
├── proto/                  # Proto文件
│   ├── user.proto
│   ├── product.proto
│   └── validate/          # validate.proto
├── gen/
│   └── go/               # 生成的代码
├── internal/
│   ├── validator/        # 验证逻辑
│   │   ├── interceptor.go
│   │   ├── custom.go
│   │   └── i18n.go
│   └── server/
├── api/                  # API定义
├── config/              # 配置文件
├── go.mod
└── Makefile
```

### **2\. Makefile示例**

```makefile
.PHONY: proto generate build test

PROTO_DIR=proto
GEN_DIR=gen/go
VALIDATE_PATH=$(shell go list -m -f '{{.Dir}}' github.com/envoyproxy/protoc-gen-validate)/validate

proto:
	@echo "生成代码..."
	protoc \
		--proto_path=$(PROTO_DIR) \
		--proto_path=. \
		--proto_path=$(VALIDATE_PATH) \
		--go_out=$(GEN_DIR) \
		--go-grpc_out=$(GEN_DIR) \
		--validate_out="lang=go:$(GEN_DIR)" \
		$(PROTO_DIR)/*.proto

generate: proto
	@echo "代码生成完成"

test:
	go test ./... -v

bench:
	go test ./... -bench=. -benchmem
```

## **十、常见问题**

### **1\. 导入validate.proto失败**

```bash
# 解决方案：确保validate.proto在正确路径
# 1. 下载validate.proto
wget -P proto/validate https://raw.githubusercontent.com/envoyproxy/protoc-gen-validate/main/validate/validate.proto

# 2. 更新protoc命令
protoc --proto_path=proto --proto_path=. --proto_path=$(go env GOPATH)/pkg/mod/github.com/envoyproxy/protoc-gen-validate@v0.10.1
```

### **2\. 验证规则不生效**

```protobuf
// 检查是否正确导入
import "validate/validate.proto";

// 检查语法
string field = 1 [
  (validate.rules).string = {
    min_len: 3  // 注意：不是 minLen
  }
];
```

### **3\. 性能问题**

```go
// 1. 使用缓存
var validateCache sync.Pool

// 2. 避免重复验证
type validatedRequest struct {
    once sync.Once
    err  error
    req  interface{ Validate() error }
}

func (v *validatedRequest) Validate() error {
    v.once.Do(func() {
        v.err = v.req.Validate()
    })
    return v.err
}
```

## **十一、与其他工具集成**

### **1\. 与Swagger/OpenAPI集成**

```protobuf
// 添加Swagger注解
message User {
  uint64 id = 1 [
    (validate.rules).uint64.gt = 0,
    (grpc.gateway.protoc_gen_openapiv2.options.openapiv2_field) = {
      description: "用户ID"
    }
  ];
}
```

### **2\. 与GORM集成**

```go
// 在GORM模型中使用
type UserModel struct {
    ID       uint64 `gorm:"primaryKey" validate:"gt=0"`
    Username string `gorm:"size:20" validate:"min=3,max=20"`
    Email    string `gorm:"uniqueIndex" validate:"email"`
}

// 保存前验证
func (u *UserModel) BeforeSave(tx *gorm.DB) error {
    // 转换为protobuf消息验证
    pbUser := &pb.User{
        Id:       u.ID,
        Username: u.Username,
        Email:    u.Email,
    }
    
    if err := pbUser.Validate(); err != nil {
        return err
    }
    
    return nil
}
```