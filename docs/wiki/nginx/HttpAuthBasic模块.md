# 基本模块
## HttpAuthBasic模块
该模块可以使你使用用户名和密码基于 HTTP 基本认证方法来保护你的站点或其部分内容。

__实例配置__
```
location / {
    auth_basic on;
    auth_basic_user_file /etc/yourpass_file;
}
```

__auth_basic__
文件格式类似于下面的内容：
```
用户名:密码
用户名2:密码2:注释
用户名3:密码3
```

__auth_basic_user_file__
密码必须使用函数 crypt(3) 加密。 你可以使用来自 Apache 的 htpasswd 工具来创建密码文件。

你也可以使用perl 创建密码文件,pw.pl 的内容：
```
#!/usr/bin/perl
use strict;

my $pw=$ARGV[0] ;
print crypt($pw,$pw)."\n";
```
然后执行
```
chmod +x pw.pl
./pw.pl password
papAq5PwY/QQM
```
papAq5PwY/QQM就是password 的crypt()密码

[原始文档](http://sysoev.ru/nginx/docs/http/ngx_http_auth_basic_module.html)