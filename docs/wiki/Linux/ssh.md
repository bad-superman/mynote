# ssh
## ssh自动登陆
1. ssh-keygen 生成公钥，私钥
2. 拷贝公钥到服务器
```
#使用ssh-copy-id
ssh-copy-id -i .ssh/id_rsa.pub root@server_ip
```
3. ssh root@server_ip 免密登陆