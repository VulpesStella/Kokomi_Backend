# Kokomi_API Project

本项目主要用于实现对不同类型游戏 API 接口返回数据处理和封装，返回标准化后的数据

## 核心架构设计

由于游戏 API 存在较高的跨地域请求延迟，本项目采用了分布式地区部署方案

- 完整服务由 1 台主节点和 5 台子节点组成，子节点汇总必要数据发送给主节点
- 子节点的物理地址分别位于`亚洲` `欧洲` `北美` `俄罗斯` `中国`，以对应游戏的 5 个区服
- 各子节点仅负责请求并处理所属地区的数据，避免跨区请求以保证效率
- 各子节点对原始 API 数据进行处理或者储存，返回经过处理后的标准化数据
- 各子节点均不对外暴露，仅允许主节点 和 Root 用户进行远程访问

## Dev 环境部署

> **⚠️ 仅适用于部署本地开发环境**

### 部署前提

1. 确保 Python >= 3.10
2. 部署在本地的 MySQL + Redis + RabbitMQ

### 虚拟环境配置

本项目采用虚拟环境管理配置，请不要直接安装包到本地环境中

```bash
# 生产环境下的必要模块：
#     API本体：fastapi uvicorn jinja2
#     ENV加载：python-dotenv
#     网络请求：httpx requests
#     数据库：aiomysql dbutils
#     中间件：redis celery
#     进度条：tqdm
#     
# 
# 开发环境下的额外模块
#     汉化支持：polib

# 创建虚拟环境
python -m venv .venv
# 激活虚拟环境
.venv/Scripts/activate    # windows
# 在虚拟环境中安装所需依赖
pip install -r requirements-dev.txt

# 复制 env.example 并重命名为 env.dev
# 完成 env.dev 文件中的所有配置项
```

### 项目初始化

```bash
# 执行数据库初始化脚本
python init/rebuild_db.py

# 执行项目初始化脚本
# 参数1 region: asia, eu, na, ru, cn
# 参数2 location: 服务器的物理地址
python init/setup.py -r <region> -l <city>,<country>

# 写入船只基本数据
python init/insert_clan.py
```

### 运行代码

```bash
# 加载本地测试用户集，请按照以下顺序启动服务

# 通过读取当前赛季工会战排名，获取到数百个工会ID
python scripts/season/main.py

# 启动 Celery 消费者
celery --app tasks.main:celery_app worker -Q refresh_queue -P solo --loglevel=info --concurrency=1

# 加载用户集（通过读取工会ID下的用户列表）
python scripts/maintenance/main.py 

# 加载用户的缓存数据
python scripts/cache/main.py 

# 待加载完所有的用户的缓存数据后执行
# 统计船只的服务器玩家数据
python scripts/stats/main.py 
```

## Prod 环境部署

> **⚠️ 仅支持通过 Docker 部署本项目**

### 拉取代码

```bash
# 以下默认以ubuntu身份登录

# 创建并进入项目目录
mkdir -p ~/kokomi && cd ~/kokomi
# 检查git
git --version
# 拉取代码
git clone https://github.com/SangonomiyaKoko/Kokomi_Backend.git
cd Kokomi_Backend
# 拉取最新代码
git pull origin main
# 丢弃修改
git restore .
git reset --hard  # 旧版
```

### 项目配置

```bash
# 复制模板文件
cp env.example env.prod
# 使用 vim 编辑配置
vim env.prod
```

### 环境配置

> 项目中生成环境使用到的模块：`fastapi` `uvicorn` `httpx` `aiomysql` `redis` `celery` `jinja2` `python-dotenv` `dbutils` `requests` `tqdm`

> 项目中测试环境使用到的模块：`polib` `pandas` `numpy` `msgpack`

```bash
# 更新系统包索引并安装必要组件
sudo apt update
sudo apt install -y python3-pip python3.12-venv
# 创建虚拟环境
python3 -m venv .venv
# 激活虚拟环境
source .venv/bin/activate # linux
# 安装依赖
pip install --upgrade pip
pip install --no-cache-dir -r requirements-dev.txt
```

### 项目初始化

> 如果本地部署有 mysql 实例为防止端口冲突，

**请务必按照以下顺序部署，后续**

```bash
# 初始化mysql数据库
docker compose up -d mysql
# 执行项目和数据库初始化脚本
# Region可选: asia, eu, na, ru, cn
python init/setup.py -r <region> -e <env_file>
# 初始化redis数据库
docker compose up -d redis
# 初始化RabbitMQ
docker compose up -d rabbitmq
# 构建项目镜像
docker build -t myapp:latest .
```

> [!IMPORTANT] > **关于 init_marker.json**：
> 初始化完成后，系统会在 `data/json` 目录下生成 `init_marker.json`。
> **请勿修改或删除此文件**，否则会导致应用逻辑异常。

### 冷启动/热启动

项目初始化完成后的数据库并没有游戏玩家或者工会的数据，可以通过两种方式实现启动

#### 冷启动

该方法主要适用于本地测试环节

启动原理：

1. 通过读取最新赛季的工会排名获取所有参与排名工会的 id
2. 依次读取工会 id 下玩家列表的 id 列表

该启动方式可以向数据库中添加大概几万个的玩家数据和几百个工会数据

```bash
# 请求获取工会战排行榜的所有工会
python3 scripts/scheduler/clan/main.py
# 依次请求并写入工会内所有的玩家id
python3 scripts/scheduler/users/main.py
```

#### 热启动

该方法基于旧数据库储存的玩家 id 列表进行存量写入

启动原理：

1. 导出旧数据库数据，由 tests/init_read.py 请求用户数据
2. 由 tests/init_write.py 将上一步请求的数据写入数据库

该方法适用于生成环境下，几十万用户数据的迁移

### 启动 Docker

```bash
# 检查Docker
systemctl status docker
# 进去项目文件夹
cd Kokomi_Backend
# 构建镜像
docker-compose build
# 前台启动（测试用）
docker-compose up
# 后台启动
docker-compose up -d
# 查看日志
docker-compose logs -f
# 容器状态
docker-compose ps
# 重构容器
docker-compose up -d --build
```
```

```