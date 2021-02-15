# nginx配置https及证书
## 设置站点
```
    server {
        listen       80;
        server_name  www.xxx.com;
        #将所有HTTP请求通过rewrite指令重定向到HTTPS。
        rewrite ^(.*)$ https://$host$1;
        #charset koi8-r;

        #access_log  logs/host.access.log  main;

        location / {
            root /usr/share/nginx/html;
            index  index.html index.htm;
        }

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }
    }
```
## 证书配置
```
server {
    listen 443;
    ssl on;
    #配置HTTPS的默认访问端口为443。
    #如果未在此处配置HTTPS的默认访问端口，可能会造成Nginx无法启动。
    #如果您使用Nginx 1.15.0及以上版本，请使用listen 443 ssl代替listen 443和ssl on。
    server_name www.tradebong.com; #需要将xxxx.com替换成证书绑定的域名。
    root html;
    index index.html index.htm;
    ssl_certificate /root/cert/xxx.pem;  #需要将cert-file-name.pem替换成已上传的证书文件的名称。
    ssl_certificate_key /root/cert/xxx.key; #需要将cert-file-name.key替换成已上传的证书密钥文件的名称。
    ssl_session_timeout 5m;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE:ECDH:AES:HIGH:!NULL:!aNULL:!MD5:!ADH:!RC4;
    #表示使用的加密套件的类型。
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2; #表示使用的TLS协议的类型。
    ssl_prefer_server_ciphers on;
    location / {
        #root   /;  #站点目录。
        index index.html index.htm;
    }
}
```

[资料](https://blog.csdn.net/duyusean/article/details/79348613)