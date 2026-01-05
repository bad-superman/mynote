# 📘 Protocol Buffers 3 语法完全指南

## 📄 **1\. 基础语法结构**

### **文件开头声明**

```protobuf
// 必需：指定语法版本
syntax = "proto3";

// 可选：包名（防止命名冲突）
package mypackage.v1;

// 必需（对Go）：生成的Go包路径
option go_package = "github.com/user/project/gen/go/mypackage/v1;mypackagev1";

// 其他语言选项
option java_multiple_files = true;
option java_package = "com.example.mypackage.v1";
option csharp_namespace = "Example.MyPackage.V1";
```

### **注释规范**

```protobuf
// 单行注释
message User {
  // 字段注释
  string id = 1;
  
  /*
   * 多行注释
   * 用于复杂说明
   */
  string name = 2;
}

/// 文档注释（部分工具支持）
/// 用户服务接口
service UserService {
  rpc GetUser(GetUserRequest) returns (User);
}
```

## 📦 **2\. 基本数据类型**

### **标量类型**

```protobuf
message ScalarTypes {
  // 数字类型
  double double_field = 1;   // 双精度浮点数
  float float_field = 2;     // 单精度浮点数
  
  // 整数类型
  int32 int32_field = 3;     // 变长编码，负值效率低
  int64 int64_field = 4;     // 变长编码，负值效率低
  uint32 uint32_field = 5;   // 无符号变长编码
  uint64 uint64_field = 6;   // 无符号变长编码
  sint32 sint32_field = 7;   // 变长编码，负值效率高
  sint64 sint64_field = 8;   // 变长编码，负值效率高
  fixed32 fixed32_field = 9; // 固定4字节，大于2^28时效率高
  fixed64 fixed64_field = 10;// 固定8字节，大于2^56时效率高
  sfixed32 sfixed32_field = 11; // 固定4字节
  sfixed64 sfixed64_field = 12; // 固定8字节
  
  // 布尔类型
  bool bool_field = 13;
  
  // 字符串类型
  string string_field = 14;  // UTF-8 或 7-bit ASCII
  
  // 字节类型
  bytes bytes_field = 15;    // 任意二进制数据
}
```

### **默认值规则**

```protobuf
// proto3 中所有字段都有默认值，无法区分"未设置"和"默认值"
message DefaultValues {
  string name = 1;           // 默认: "" (空字符串)
  int32 count = 2;           // 默认: 0
  bool active = 3;           // 默认: false
  repeated string tags = 4;  // 默认: [] (空列表)
  Color color = 5;           // 默认: 第一个枚举值(必须为0)
}

enum Color {
  COLOR_UNSPECIFIED = 0;  // 必须定义0值作为默认
  COLOR_RED = 1;
  COLOR_GREEN = 2;
}
```

## 🏗️ **3\. 复合数据类型**

### **消息定义**

```protobuf
// 基本消息
message Person {
  string id = 1;
  string name = 2;
  string email = 3;
  int32 age = 4;
}

// 嵌套消息
message Company {
  string id = 1;
  string name = 2;
  
  // 内嵌消息定义
  message Address {
    string street = 1;
    string city = 2;
    string country = 3;
  }
  
  Address address = 3;
  
  // 引用外部消息
  repeated Person employees = 4;
}

// 使用嵌套消息
Company.Address companyAddress = 1;
```

### **数组/列表**

```protobuf
message ListExample {
  // 重复字段（数组）
  repeated string tags = 1;
  repeated int32 scores = 2;
  repeated Person people = 3;
  
  // 二维数组（通过嵌套消息实现）
  message Row {
    repeated int32 cells = 1;
  }
  repeated Row matrix = 4;
}
```

### **映射类型**

```protobuf
message MapExample {
  // 键类型只能是整数或字符串
  map<string, string> properties = 1;
  map<int32, string> id_to_name = 2;
  map<string, Person> username_to_person = 3;
  
  // map<string, repeated string> 不允许
  // 替代方案：
  message StringList {
    repeated string values = 1;
  }
  map<string, StringList> tags_by_category = 4;
}
```

### **枚举类型**

```protobuf
enum UserRole {
  // 必须从0开始
  USER_ROLE_UNSPECIFIED = 0;  // 约定：使用UNSPECIFIED作为0值
  USER_ROLE_GUEST = 1;
  USER_ROLE_USER = 2;
  USER_ROLE_ADMIN = 3;
  USER_ROLE_SUPER_ADMIN = 4;
  
  // 可以预留值
  reserved 5 to 10;
  reserved "DEPRECATED_ROLE";
}

// 枚举别名（相同值的不同名称）
enum Status {
  STATUS_UNKNOWN = 0;
  STATUS_ACTIVE = 1;
  STATUS_INACTIVE = 2;
  STATUS_ENABLED = 1;  // STATUS_ACTIVE的别名
}
```

## 🔄 **4\. 高级特性**

### **Oneof 字段**

```protobuf
message Notification {
  string id = 1;
  int64 timestamp = 2;
  
  // 互斥的字段，同一时间只能设置一个
  oneof content {
    string text = 3;
    Image image = 4;
    Video video = 5;
    Audio audio = 6;
  }
  
  oneof priority {
    bool high_priority = 7;
    bool urgent = 8;
  }
}

// 注意：oneof 字段不能是 repeated
```

### **保留字段**

```protobuf
message User {
  // 保留字段编号（防止重用）
  reserved 2, 15 to 20;  // 保留字段号
  reserved "surname", "age";  // 保留字段名
  
  string id = 1;
  string name = 3;  // 跳过保留的2
  // string surname = 4;  // 错误：字段名被保留
}
```

### **JSON 映射**

```protobuf
message JsonExample {
  // 自定义JSON字段名
  string user_id = 1 [json_name = "userId"];
  string full_name = 2 [json_name = "fullName"];
  
  // 默认映射规则：
  // message_name → messageName
  // field_name → fieldName
  // repeated → 数组
  // map → 对象
}
```

## 🛠️ **5\. 服务定义**

### **服务基础**

```protobuf
// 服务定义
service UserService {
  // 一元RPC（请求-响应）
  rpc GetUser(GetUserRequest) returns (User);
  
  // 服务端流式RPC
  rpc ListUsers(ListUsersRequest) returns (stream User);
  
  // 客户端流式RPC
  rpc CreateUsers(stream CreateUserRequest) returns (CreateUsersResponse);
  
  // 双向流式RPC
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

// 请求/响应消息
message GetUserRequest {
  string user_id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
}
```

## 📚 **6\. 导入和包管理**

### **导入语法**

```protobuf
// 导入其他.proto文件
import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";
import "google/protobuf/wrappers.proto";

// 公共导入
import public "common.proto";  // 可被导入此文件的其他文件使用

// 使用导入的类型
message Event {
  string id = 1;
  google.protobuf.Timestamp created_at = 2;
  google.protobuf.StringValue description = 3;
}
```

### **包和命名空间**

```protobuf
// 声明包
package company.product.v1;

// 使用完全限定名
message MyMessage {
  // 使用其他包的类型
  company.product.v2.CommonType common = 1;
  
  // 简写（在同一包内）
  CommonType local_common = 2;
}
```

## ⚙️ **7\. 选项和注解**

### **字段选项**

```protobuf
import "google/protobuf/descriptor.proto";

message AdvancedMessage {
  // 弃用字段
  string old_field = 1 [deprecated = true];
  
  // 自定义选项（需要先定义）
  string secret_field = 2 [
    sensitive = true,  // 自定义选项
    json_name = "secretField"
  ];
  
  // 验证规则（使用protoc-gen-validate）
  string email = 3 [(validate.rules).string.email = true];
  int32 age = 4 [(validate.rules).int32 = {gt: 0, lt: 150}];
}

// 定义自定义选项
extend google.protobuf.FieldOptions {
  bool sensitive = 50000;
}
```

### **消息和枚举选项**

```protobuf
// 消息选项
message Config {
  option (my_option) = "value";
  
  string name = 1;
}

// 枚举选项
enum LogLevel {
  option allow_alias = true;  // 允许枚举值别名
  
  LOG_LEVEL_UNSPECIFIED = 0;
  LOG_LEVEL_DEBUG = 1;
  LOG_LEVEL_INFO = 2;
  LOG_LEVEL_WARNING = 3;
  LOG_LEVEL_ERROR = 4;
  LOG_LEVEL_FATAL = 5;
  LOG_LEVEL_PANIC = 5;  // FATAL的别名
}
```

## 📋 **8\. 完整示例**

```protobuf
syntax = "proto3";

package ecommerce.v1;

import "google/protobuf/timestamp.proto";
import "google/protobuf/wrappers.proto";
import "validate/validate.proto";

option go_package = "github.com/company/ecommerce/gen/go/ecommerce/v1;ecommercev1";
option java_multiple_files = true;
option java_package = "com.company.ecommerce.v1";

// 枚举定义
enum OrderStatus {
  ORDER_STATUS_UNSPECIFIED = 0;
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_PROCESSING = 2;
  ORDER_STATUS_SHIPPED = 3;
  ORDER_STATUS_DELIVERED = 4;
  ORDER_STATUS_CANCELLED = 5;
  ORDER_STATUS_REFUNDED = 6;
}

enum PaymentMethod {
  PAYMENT_METHOD_UNSPECIFIED = 0;
  PAYMENT_METHOD_CREDIT_CARD = 1;
  PAYMENT_METHOD_PAYPAL = 2;
  PAYMENT_METHOD_BANK_TRANSFER = 3;
}

// 消息定义
message Product {
  string id = 1 [(validate.rules).string.uuid = true];
  string name = 2 [(validate.rules).string = {min_len: 1, max_len: 100}];
  string description = 3;
  Category category = 4;
  Money price = 5;
  int32 stock = 6;
  bool active = 7;
  google.protobuf.Timestamp created_at = 8;
  google.protobuf.Timestamp updated_at = 9;
  map<string, string> attributes = 10;
  
  message Category {
    string id = 1;
    string name = 2;
    string slug = 3;
  }
}

message Money {
  string currency_code = 1 [(validate.rules).string.len = 3];
  int64 units = 2;  // 整数部分
  int32 nanos = 3;  // 小数部分（10^-9）
}

message Order {
  string id = 1;
  string customer_id = 2;
  OrderStatus status = 3;
  repeated OrderItem items = 4;
  Money total_amount = 5;
  Address shipping_address = 6;
  PaymentMethod payment_method = 7;
  google.protobuf.Timestamp order_date = 8;
  google.protobuf.Timestamp estimated_delivery = 9;
  
  message OrderItem {
    string product_id = 1;
    string product_name = 2;
    int32 quantity = 3 [(validate.rules).int32.gt = 0];
    Money unit_price = 4;
    Money total_price = 5;
  }
}

message Address {
  string line1 = 1 [(validate.rules).string.min_len = 1];
  google.protobuf.StringValue line2 = 2;
  string city = 3 [(validate.rules).string.min_len = 1];
  string state = 4;
  string postal_code = 5;
  string country = 6 [(validate.rules).string.len = 2];
  
  oneof type {
    bool is_residential = 7;
    bool is_business = 8;
  }
}

// 服务定义
service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (Order);
  rpc GetOrder(GetOrderRequest) returns (Order);
  rpc ListOrders(ListOrdersRequest) returns (ListOrdersResponse);
  rpc UpdateOrderStatus(UpdateOrderStatusRequest) returns (Order);
  rpc StreamOrderUpdates(StreamOrderUpdatesRequest) returns (stream OrderUpdate);
  
  // 批量操作
  rpc BatchCreateOrders(stream CreateOrderRequest) returns (BatchCreateOrdersResponse);
}

// 请求/响应消息
message CreateOrderRequest {
  string customer_id = 1 [(validate.rules).string.uuid = true];
  repeated OrderItem items = 2 [(validate.rules).repeated.min_items = 1];
  Address shipping_address = 3;
  PaymentMethod payment_method = 4;
}

message ListOrdersRequest {
  string customer_id = 1;  // 可选过滤
  repeated OrderStatus status_filter = 2;
  google.protobuf.Timestamp from_date = 3;
  google.protobuf.Timestamp to_date = 4;
  int32 page_size = 5 [(validate.rules).int32 = {gte: 1, lte: 100}];
  string page_token = 6;
}

message ListOrdersResponse {
  repeated Order orders = 1;
  string next_page_token = 2;
  int32 total_count = 3;
}

message OrderUpdate {
  string order_id = 1;
  OrderStatus new_status = 2;
  google.protobuf.Timestamp updated_at = 3;
  string message = 4;
}
```

## 💡 **9\. 重要注意事项**

### **语法规则总结**

1.  **字段编号**：1-15 占用1字节，16-2047 占用2字节
    
2.  **字段规则**：proto3 只有 `repeated`，没有 `required`/`optional`
    
3.  **默认值**：无法检测字段是否被设置 vs 显式设置为默认值
    
4.  **枚举**：必须包含值为0的枚举项作为默认值
    
5.  **服务**：必须定义请求和响应消息，不能使用标量类型
    
6.  **兼容性**：不能修改已使用字段的编号或类型
    

### **性能最佳实践**

```protobuf
// 1. 常用字段使用1-15的编号
message OptimizedMessage {
  string id = 1;           // 常用字段用小编号
  string name = 2;
  int32 priority = 3;
  repeated string tags = 16;  // 不常用字段用大编号
  map<string, string> metadata = 17;
}

// 2. 避免过度嵌套
// 3. 合理使用 repeated 和 map
// 4. 考虑使用 oneof 替代多个可选字段
```

### **工具命令示例**

```bash
# 1. 生成Go代码
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       *.proto

# 2. 生成多种语言
protoc \
  --go_out=gen/go \
  --java_out=gen/java \
  --python_out=gen/python \
  --js_out=gen/js \
  *.proto

# 3. 使用Buf工具
buf lint      # 代码检查
buf generate  # 生成代码
buf breaking  # 检查破坏性变更
```