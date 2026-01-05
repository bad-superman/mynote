# 🎭 Playwright 简洁使用教程

## 📦 **1\. 安装与配置**

### **安装**

```bash
# 安装 Playwright
pip install playwright

# 安装浏览器（推荐）
playwright install          # 安装所有浏览器
playwright install chromium # 只安装 Chromium

# 安装 Pytest 集成（可选）
pip install pytest-playwright
```

### **验证安装**

```python
# 验证脚本
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.google.com")
    print(f"页面标题: {page.title()}")
    browser.close()
```

## 🚀 **2\. 核心概念速查**

### **三种浏览器引擎**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Chromium (Google Chrome/Edge 基础)
    browser = p.chromium.launch()
    
    # Firefox
    browser = p.firefox.launch()
    
    # WebKit (Safari 基础)
    browser = p.webkit.launch()
```

### **同步 vs 异步 API**

```python
# 同步 API（推荐初学者）
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    browser.close()

# 异步 API
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")
        await browser.close()

asyncio.run(main())
```

## 🎯 **3\. 基础操作**

### **页面导航**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # 显示浏览器
    page = browser.new_page()
    
    # 基本导航
    page.goto("https://example.com")  # 跳转
    page.reload()                     # 刷新
    page.go_back()                    # 后退
    page.go_forward()                 # 前进
    
    # 等待策略
    page.goto("https://example.com", wait_until="networkidle")  # 网络空闲
    page.goto("https://example.com", wait_until="domcontentloaded")  # DOM加载
    page.goto("https://example.com", wait_until="load")  # 页面完全加载
    
    # 获取页面信息
    title = page.title()            # 标题
    url = page.url                  # 当前URL
    content = page.content()        # HTML内容
    
    browser.close()
```

### **元素定位与交互**

```python
# 定位方法（最常用的）
page.click("button#submit")                    # 点击
page.fill("input[name='username']", "admin")   # 填写表单
page.type("textarea", "Hello World")           # 模拟打字
page.press("input", "Enter")                   # 按键

# 多种选择器
page.click("#id")                       # ID
page.click(".class")                    # 类名
page.click("text=Login")                # 文本内容
page.click("button:has-text('Submit')") # 包含文本
page.click("input[name='email']")       # 属性
page.click("//button[@type='submit']")  # XPath

# 等待元素
page.wait_for_selector("#loading", state="hidden")  # 等待隐藏
page.wait_for_selector(".result", state="visible")  # 等待显示
page.wait_for_timeout(3000)                         # 强制等待（不推荐）
```

### **表单操作**

```python
# 表单填写
page.fill("#username", "testuser")
page.fill("#password", "password123")
page.select_option("#country", "US")            # 下拉框
page.check("#agree-terms")                      # 勾选
page.uncheck("#newsletter")                     # 取消勾选
page.set_checked("#remember", True)             # 设置复选框状态

# 文件上传
page.set_input_files("input[type='file']", "path/to/file.pdf")

# 提交表单
page.click("button[type='submit']")
# 或
page.press("#password", "Enter")
```

## 🔍 **4\. 高级元素操作**

### **多种定位方式**

```python
# 单元素定位
element = page.query_selector(".item")          # 第一个匹配元素
element = page.locator(".item").first          # 使用locator

# 多元素定位
elements = page.query_selector_all(".item")     # 所有匹配元素
elements = page.locator(".item").all()         # 使用locator

# 精确的文本定位
page.click("text=Submit")                      # 精确文本
page.click("text=/submit/i")                   # 正则匹配
page.click("text='Log in'")                    # 包含文本

# 相对定位
page.locator("form").locator("button").click()  # 在form中找button
```

### **元素状态检查**

```python
# 检查可见性
is_visible = page.is_visible("#element")
is_hidden = page.is_hidden("#element")

# 检查存在
is_present = page.locator("#element").count() > 0

# 检查状态
is_enabled = page.is_enabled("button")
is_checked = page.is_checked("#checkbox")
is_editable = page.is_editable("input")

# 获取属性
text = page.text_content(".title")              # 文本内容
value = page.input_value("#input")              # 输入值
attribute = page.get_attribute("img", "src")    # 属性值
```

## 📊 **5\. 页面等待策略**

### **智能等待**

```python
# 等待元素出现
page.wait_for_selector(".result")

# 等待元素状态
page.wait_for_selector("#loading", state="hidden")    # 等待消失
page.wait_for_selector("#content", state="visible")   # 等待显示
page.wait_for_selector("#button", state="enabled")    # 等待可用

# 等待函数
page.wait_for_function("window.dataLoaded")          # JS函数返回true
page.wait_for_function("document.querySelectorAll('.item').length > 5")

# 等待事件
page.wait_for_event("load")                          # 页面加载
page.wait_for_event("domcontentloaded")

# 组合等待
from playwright.sync_api import expect
expect(page.locator(".result")).to_be_visible()
expect(page.locator("#count")).to_have_text("10")
expect(page.locator("#status")).to_have_value("completed")
```

### **超时控制**

```python
# 全局超时
context.set_default_timeout(30000)  # 30秒

# 单个操作超时
page.click("button", timeout=10000)            # 10秒
page.wait_for_selector(".item", timeout=5000)  # 5秒

# 自定义重试逻辑
import time
for attempt in range(3):
    try:
        page.click("#unstable-button", timeout=2000)
        break
    except:
        if attempt == 2:
            raise
        time.sleep(1)
```

## 🌐 **6\. 网络与请求处理**

### **拦截请求**

```python
# 请求拦截
def handle_request(route, request):
    if "analytics" in request.url:
        route.abort()  # 阻止请求
    else:
        route.continue_()

page.route("**/*", handle_request)

# 修改响应
def handle_response(route, request):
    response = route.fulfill(
        status=200,
        content_type="text/html",
        body="<html><body>Custom Response</body></html>"
    )

page.route("**/api/data", handle_response)

# 移除拦截
page.unroute("**/*", handle_request)
```

### **API 测试**

```python
# 监听网络请求
api_responses = []

def log_response(response):
    if "/api/" in response.url:
        api_responses.append(response)

page.on("response", log_response)

# 获取请求数据
request = page.wait_for_request("**/api/login")
print(f"Method: {request.method}")
print(f"Headers: {request.headers}")
print(f"Post Data: {request.post_data}")

# 获取响应数据
response = page.wait_for_response("**/api/data")
print(f"Status: {response.status}")
print(f"Body: {response.json()}")
```

## 📁 **7\. 文件与下载**

### **文件下载**

```python
# 等待下载
with page.expect_download() as download_info:
    page.click("a.download-link")
    
download = download_info.value
path = download.path()                      # 临时路径
save_path = f"downloads/{download.suggested_filename}"
download.save_as(save_path)                # 保存文件

# 自动接受下载
context = browser.new_context(
    accept_downloads=True
)
```

### **截图与PDF**

```python
# 截图
page.screenshot(path="screenshot.png")           # 全屏
page.screenshot(path="element.png", clip={"x": 10, "y": 10, "width": 100, "height": 100})
element.screenshot(path="button.png")            # 元素截图

# PDF导出
page.pdf(path="page.pdf", format="A4")
```

## 🧪 **8\. 测试框架集成**

### **Pytest 示例**

```python
# test_example.py
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="function")
def page(context):
    page = context.new_page()
    yield page
    page.close()

def test_login(page: Page):
    """测试登录功能"""
    page.goto("https://example.com/login")
    
    page.fill("#username", "testuser")
    page.fill("#password", "password123")
    page.click("#login-button")
    
    # 使用expect进行断言
    expect(page).to_have_url("https://example.com/dashboard")
    expect(page.locator(".welcome")).to_have_text("Welcome, testuser!")

def test_search(page: Page):
    """测试搜索功能"""
    page.goto("https://example.com")
    
    page.fill("[placeholder='Search']", "Playwright")
    page.press("[placeholder='Search']", "Enter")
    
    # 等待并验证结果
    results = page.locator(".search-result")
    expect(results).to_have_count(10)
```

### **测试配置**

```python
# conftest.py
import pytest
from playwright.sync_api import Playwright, Browser, BrowserContext

@pytest.fixture(scope="session")
def playwright():
    with sync_playwright() as p:
        yield p

@pytest.fixture(scope="session")
def browser(playwright: Playwright):
    browser = playwright.chromium.launch(
        headless=True,      # 无头模式
        slow_mo=50,         # 慢动作（调试用）
        devtools=True       # 打开开发者工具
    )
    yield browser
    browser.close()

@pytest.fixture
def context(browser: Browser):
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York"
    )
    yield context
    context.close()
```

## 🛡️ **8\. 最佳实践**

### **代码组织**

```python
# page_objects/login_page.py
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.username_input = page.locator("#username")
        self.password_input = page.locator("#password")
        self.login_button = page.locator("#login-button")
        self.error_message = page.locator(".error")
    
    def navigate(self):
        self.page.goto("https://example.com/login")
    
    def login(self, username, password):
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
    
    def get_error(self):
        return self.error_message.text_content()

# 使用示例
def test_login():
    page = browser.new_page()
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login("user", "pass")
    assert login_page.get_error() == "Invalid credentials"
```

### **配置管理**

```yaml
# playwright.config.py
import pytest
from playwright.sync_api import Browser, BrowserContext

def pytest_configure(config):
    config.option.headless = True
    config.option.screenshot = "only-on-failure"
    config.option.video = "retain-on-failure"

@pytest.fixture
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "record_video_dir": "videos/"
    }
```

## 🚨 **9\. 常见问题解决**

### **调试技巧**

```python
# 1. 暂停调试
page.pause()  # 打开Playwright Inspector

# 2. 控制台输出
page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))

# 3. 详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 4. 慢动作模式
browser = p.chromium.launch(headless=False, slow_mo=1000)

# 5. 录制脚本
playwright codegen https://example.com
```

### **常见错误处理**

```python
try:
    page.click("#unstable-element", timeout=3000)
except TimeoutError:
    print("元素未找到，尝试其他方式")
    page.reload()
    page.wait_for_selector("#unstable-element", state="visible")
    page.click("#unstable-element")

# 处理弹窗
page.on("dialog", lambda dialog: dialog.accept())

# 处理框架
frame = page.frame(name="iframe-name")
frame.click("button")
```

## 📋 **10\. 速查表**

| 任务  | 代码示例 |
| --- | --- |
| **启动浏览器** | `browser = p.chromium.launch(headless=False)` |
| **新建页面** | `page = browser.new_page()` |
| **页面跳转** | `page.goto("https://example.com")` |
| **点击元素** | `page.click("button#submit")` |
| **填写表单** | `page.fill("input[name='email']", "test@example.com")` |
| **获取文本** | `text = page.text_content(".title")` |
| **等待元素** | `page.wait_for_selector(".result")` |
| **截图** | `page.screenshot(path="screenshot.png")` |
| **执行JS** | `page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` |
| **获取URL** | `current_url = page.url` |

## 🎯 **快速开始模板**

```python
#!/usr/bin/env python3
"""
Playwright 快速开始模板
"""

from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        # 1. 启动浏览器
        browser = p.chromium.launch(
            headless=False,      # 显示浏览器窗口
            slow_mo=100,         # 慢动作，方便观察
        )
        
        # 2. 创建页面
        page = browser.new_page()
        
        # 3. 设置视口大小
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            # 4. 访问网站
            page.goto("https://www.baidu.com")
            
            # 5. 页面操作
            page.fill("#kw", "Playwright教程")
            page.press("#kw", "Enter")
            
            # 6. 等待结果
            page.wait_for_selector(".result")
            
            # 7. 获取数据
            results = page.query_selector_all(".result h3 a")
            for result in results[:5]:
                print(f"标题: {result.text_content()}")
                print(f"链接: {result.get_attribute('href')}")
                
            # 8. 截图
            page.screenshot(path="search_results.png")
            
        finally:
            # 9. 关闭浏览器
            browser.close()

if __name__ == "__main__":
    main()
```