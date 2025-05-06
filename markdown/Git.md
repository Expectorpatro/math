# Git

```
git config --global user.name "Expector"
git config --global user.email 19975022383@163.com
省略了Local，表示这是本地配置，只对本地仓库有效
--global:全局配置，对所有仓库生效
--system:系统配置，对所有用户生效
```

使得提交文件时能够识别是谁提交的

保存用户名及密码

```
git config --global credential.helper store
```

查看git的配置信息

```
git config --list
```

新建仓库

```
# 进入某个路径，输入以下代码，该路径即成为一个仓库
git init
# 从远程服务器上克隆一个已经存在的仓库
git clone
```

1. working directory工作区
   
   实际操作的目录，即.git文件夹所在的目录

2. staging area暂存区
   
   临时存放即将提交的修改内容，即.git/index

3. local repository本地仓库
   
   由git init创建的，存储代码和版本信息的主要位置，.git/objects

文件类型

1. Untrack未跟踪，还没有被git管理起来的文件

2. unmodified未修改，已经被git管理起来但内容为被修改的

3. modified已修改，已经被git管理起来内容也已被修改但是没有提交到暂存区的

4. stage已暂存

查看当前仓库情况

```git
git status
```

文件操作

```git
# 将文件提交到暂存区
git add
git add *.txt # 提交txt后缀的文件，add支持通配符
git add . $ 提交所有文件
# 把暂存区中的文件撤销暂存
git rm --cached

# 将暂存区中的文件提交到仓库，-m参数指定提交的信息，会被保存到仓库中
git commit -m
```

查看历史提交情况

```git
git log

commit 4329684698950f8e1b636a324732cdf4364b2507 (HEAD -> master)
Author: Expector <19975022383@163.com>
Date:   Wed Dec 18 16:35:24 2024 +0800

    提交所有其它文件

commit 2ffe335bf085181e8181adf0c951d05d819e7b2c
Author: Expector <19975022383@163.com>
Date:   Wed Dec 18 16:30:08 2024 +0800

    commit the pdf

commit bc0171408629195974559fb5ea2a1640f6e9af7e (origin/master)
Author: Expector <19975022383@163.com>
Date:   Sat Nov 23 17:16:18 2024 +0800

    提交pdf文件


git log --oneline 只显示提交号和提交信息
```

回退版本

```git
# 回退版本，并且保留工作区和暂存区的所有修改内容
git reset --soft 版本号
# 回退版本，并且丢弃工作区和暂存区的所有修改内容
git reset --hard 版本号
# 回退版本，只保留工作区的修改内容，丢弃暂存区的修改内容
git reset --mixed 版本号
# 也可以不用版本号，HEAD^表示上一个版本
git reset --soft HEAD^
# 回退完版本后，git log的输出会发生变化，也会退回到之前版本时的log
```

查看操作历史，在误操作后可以使用该命令查找误操作之前的版本号，然后使用 **`git reset`** 进行版本的回退

```git
git reflog
```

查看差异

```git
# 不加参数默认比较工作区与暂存区的差异，会显示发生更改的文件以及更改的详细信息
git diff
# 比较工作区与版本库的差异
git diff HEAD
# 比较暂存区与版本库的差异
git diff --cached
# 比较两个版本的差异，HEAD表示当前版本，HEAD~表示上一个版本
# HEAD~2表示上一个版本的再前面一个版本，以此类推
git diff 版本1id 版本2id
# 比较文件之间的差异
git diff HEAD~ HEAD 文件名
```

删除文件，工作区与暂存区同时删除，删除之后需要重新提交一次暂存区中的内容来对版本库进行更新

```git
git rm 文件名
# 只删除暂存区中的文件，不删除本地
git rm --cached 文件名
```

查看暂存区中的文件

```git
git ls-files
```

忽略文件

需要创建一个.gitignore文件，

```git
# #开头表示注释，不会被git读取
# 忽略单个文件
文件名
# 支持正则表达式，忽略某一类型的文件
*.log
# 忽略当前目录下名为temp的文件夹
/temp/
# 忽略任何目录下名为temp的文件夹
temp/
## **匹配中间目录名，忽略doc文件下所有文件夹中的pdf文件
doc/**/*.pdf
```

查看本地仓库的远程仓库配置

```git
git remote -v
```

将远程仓库与本地仓库关联

```git
git remote add 远程仓库指定的本地别名 远程仓库地址
```



在push的时候github会调用本地的ssh去寻找密钥（公私钥是ssh这个程序进行管理），只检查你本地是否拥有仓库协作者所有公钥对应的任一私钥，即git没有绑定账号，一个账号多个公私钥也没有必要，只要ssh在本地默认的ssh公私钥存储文件夹内找到对应的私钥，就可以push。邀请协作者后，github会进行记录，记录下他账号内的所有公钥，包含在这个仓库内，任意一台设备对该仓库进行push都会检查该设备是否具有对应的私钥