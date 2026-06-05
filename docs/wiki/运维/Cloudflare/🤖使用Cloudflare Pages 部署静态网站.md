**从零到上线**使用 Cloudflare Pages 部署静态网站的操作步骤，包括个人网站和前端框架（React/Vue/Next.js）通用流程。

---

## **步骤 0：准备工作**

1.  注册 Cloudflare 账号：[https://www.cloudflare.com](https://www.cloudflare.com)
    
2.  准备你的静态网站代码
    
    -   纯 HTML/CSS/JS，或者 React/Vue/Svelte 项目都可以。
        
3.  将代码放到 Git 仓库
    
    -   支持 GitHub / GitLab / Bitbucket
        
    -   建议用主分支（main / master）或者开发分支（develop）。
        

---

## **步骤 1：创建 Cloudflare Pages 项目**

1.  登录 Cloudflare → 左侧菜单选择 **Pages**。
    
2.  点击 **Create a Project**。
    
3.  选择你的 Git 仓库（Cloudflare 会要求授权 GitHub/GitLab/Bitbucket）。
    
4.  选择要部署的分支（通常是 `main` 或 `master`）。
    

---

## **步骤 2：配置构建设置**

根据你的项目类型选择：

| 类型  | 构建命令 | 输出目录 |
| --- | --- | --- |
| 纯 HTML/CSS/JS | 留空  | `/` 或 `.` |
| React (Create React App) | `npm run build` | `build` |
| Vue (Vue CLI) | `npm run build` | `dist` |
| Next.js | `npm run build && npm run export` | `out` |

⚠️ 注意：

-   如果是 Next.js，需要开启 **Static Export**，Cloudflare Pages 只托管静态文件。
    
-   确保 `package.json` 里有对应的 build 命令。
    

---

## **步骤 3：部署**

1.  点击 **Save and Deploy**。
    
2.  Cloudflare Pages 会自动拉取仓库代码，执行构建命令，并将输出目录发布到 CDN。
    
3.  构建完成后，会生成一个临时 URL，例如：
    

```text
https://your-project.pages.dev
```

-   这是一个 Cloudflare 免费提供的域名。
    

---

## **步骤 4：绑定自定义域名**

1.  在 Cloudflare Pages → 项目 → **Custom Domains**。
    
2.  点击 **Set up a custom domain** → 输入你的域名（例如 `example.com`）。
    
3.  Cloudflare 会提供 DNS 设置：
    
    -   自动添加 **CNAME 或 A 记录**。
        
4.  启用 **HTTPS**（Cloudflare 自动提供免费 SSL）。
    

✅ 绑定完成后，你的静态网站就可以通过自己域名访问了。

---

## **步骤 5：自动化部署（CI/CD）**

-   每次 **推送到指定分支**（main / develop），Cloudflare Pages 都会自动：
    
    1.  拉取最新代码
        
    2.  执行构建命令
        
    3.  更新 CDN
        
-   你不需要手动上传文件，非常适合前端持续部署。
    

---

## **步骤 6（可选）：优化**

1.  **缓存和路由**
    
    -   Cloudflare Pages 默认 CDN 缓存静态文件。
        
    -   可以配置 `_headers` 或 `_redirects` 文件，实现缓存策略和 SPA 路由。
        
2.  **环境变量**
    
    -   在 Pages 项目设置 → **Environment Variables**，可配置 API 地址等敏感信息。
        
3.  **Workers Functions**
    
    -   如果需要动态请求处理，可在 Pages + Workers 配合实现。
        

---

💡 **总结流程**

1.  准备代码 → 上传 Git
    
2.  Cloudflare Pages 创建项目 → 连接仓库
    
3.  配置构建命令 + 输出目录
    
4.  部署 → 临时域名访问
    
5.  绑定自定义域名 → 开启 HTTPS
    
6.  自动化部署 → 推送代码即上线