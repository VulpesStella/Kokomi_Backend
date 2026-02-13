# Kokomi_API Project

本文部署所使用的环境

- Ubuntu 24.04
- Python 3.12 (最低兼容3.10)

## 部署流程

本项目使用的外部依赖:

- Git
- Docker
- MySQL >= 8.0
- Redis >= 5.0
- RabbitMQ >= 4.0

> 每个依赖具体部署流程放在文尾

### 拉取代码

```bash
# 以下默认以ubuntu身份登录

# 新建项目文件夹
sudo mkdir /home/ubuntu/kokomi
cd /home/ubuntu/kokomi
# 检查git
git --version
# 拉取代码
git clone https://github.com/SangonomiyaKoko/Kokomi_Backend.git
# 拉取最新代码
git pull origin main
# 丢弃修改
git restore .
git reset --hard  # 旧版
```

### 填写配置

复制粘贴一份.env.example 文件，并重命名为.env.prod，填写相关配置文件

### 建立数据库

```bash
# 安装 pip 和 venv
sudo apt update
sudo apt install -y python3-pip
sudo apt install python3.12-venv  # 示例为3.12版本
# 创建虚拟环境
python3 -m venv .venv
# 激活虚拟环境
.venv/Scripts/activate    # windows
source .venv/bin/activate # linux
# 安装依赖
pip3 install fastapi uvicorn httpx aiomysql redis celery jinja2 python-dotenv dbutils requests cryptography
pip3 install polib pika pandas numpy msgpack
# 运行数据库初始化
python3 tests/init_mysql.py
```

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
