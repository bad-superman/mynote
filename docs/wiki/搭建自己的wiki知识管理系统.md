# 搭建自己的wiki知识管理系统

最近在网上看到使用mkdoc + git可以搭建自己wiki，试了试可以，还免费，你说说气人不  
市面上也有很多其他开源的wiki系统  
1. 大名鼎鼎的[MediaWiki](https://link.zhihu.com/?target=https%3A//www.mediawiki.org/wiki/MediaWiki)  
2. 小巧易用的[DokuWiki](https://link.zhihu.com/?target=https%3A//www.dokuwiki.org/dokuwiki)  
3. 国内开源的[minDoc](https://link.zhihu.com/?target=https%3A//github.com/lifei6671/mindoc)  
4. [Gitbook](https://link.zhihu.com/?target=https%3A//www.gitbook.com/)  
5. [Docsify](https://link.zhihu.com/?target=https%3A//docsify.js.org/)  
6. [Hexo](https://link.zhihu.com/?target=https%3A//hexo.io/)  
7. [MkDocs](https://link.zhihu.com/?target=https%3A//www.mkdocs.org/)  

小编选择使用的是MkDocs，因为它部署和使用都非常的简便，特别适合作为个人wiki知识管理系统。简单的说MkDocs就是将Markdown文件转换成静态的HTML网站，然后既可以在本地直接访问，也可以托管到服务器或者GitHub。

> 实战开始

## 1.安装MkDocs
使用pip安装
```
pip install --upgrade pip
pip install mkdocs
```

验证是否安装成功
```
mkdocs --version
```

## 2.创建一个wiki
```
mkdocs new my-wiki
cd my-wiki
```
创建成功后，如下图
![](https://pic4.zhimg.com/80/v2-b77516a9f797e457cc9152901b0a06f7_1440w.jpg)  
* docs文件夹下放着我们自己写的MarkDown文章，默认生成index.md  
* mkdocs.yml是wiki网站的配置文件（主题、目录、语言等）  

## 3.预览wiki
* 首先启动mkdocs服务
```
mkdocs serve
```
* 然后打开浏览器输入127.0.0.1:8000访问wiki
如果以上步骤都执行成功，你将看到如下界面：
![](https://pic1.zhimg.com/80/v2-174f7fa0c5d4f38f6ef54f596741705c_1440w.jpg)

## 4.更换主题
mkdocs有多个主题可供选择，以满足不用用户的喜好，在此小编向大家推荐Material主题。

* 安装Material主题
```
pip install mkdocs-material
```

* 配置wiki使用Material主题
```
theme:
  name: 'material'
```

## 5.将你的wiki站点托管到GitHub
* 创建一个新仓库。 比如: https://github.com/user_name/repository_name  
* 初始化你的本地仓库（wiki）, 添加远程仓库，提交本地修改并推送到远程仓库  
```
cd my-wiki
git init
git add remote https://github.com/user_name/repository_name
git add .
git commit -m "first commit"
git push origin master
```

* 部署你的wiki站点
```
mkdocs gh-deploy
```
现在你的wiki站点（HTML文件）在gh-pages分支，你的wiki站点（markdown文件）在master分支。  

该命令执行了两个动作：  
1. 将Mardown文件转为静态HTML网页文件  
2. 将所有的静态HTML网页文件都推送到远程仓库的gh-pages分支  

GitHub会自动管理gh-pages分支的静态网页，就相当于一个静态网站服务器。

* 通过以下网址访问你的wiki
```
https://user_name.github.io/repository_name
```