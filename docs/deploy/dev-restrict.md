# 开发环境（受限模式）部署步骤

> 适用于 Windows10/11 环境

该模式仅适用于**不涉及数据库操作**的接口开发，不要求本地部署 MySQL、Docker 等相关服务。

例如获取玩家随机基本数据接口，仅需要读取外部接口，处理后返回。

## 项目配置

复制一份文件 `env.example` 并重命名为 `env.dev`

> 仅需配置带 ★ 的配置项即可

```conf
PLATFORM="KokomiAPI-01"    # 标识符
LOG_LEVEL="debug"          # ★ log 输出级别
DEV_MODE=1                 # ★ 设置为 DEV_MODE

SSL_CA_BUNDLE=""
API_ROOT_TOKEN="root"      # ★ 默认 Root 用户的 Token
API_USER_TOKEN="user"      # ★ 默认 User 用户的 Token

SQLITE_DIR=""

MYSQL_HOST="localhost"
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=""
MYSQL_USER=""
MYSQL_PASSWORD=""
MYSQL_DATABASE="wows"

REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_PASSWORD=""
REDIS_DATABASE=0

RABBITMQ_HOST="localhost"
RABBITMQ_DEFAULT_USER=""
RABBITMQ_DEFAULT_PASS=""
```

## 初始化

```bash
# 执行项目初始化脚本
# 参数1 region: 可选值 [asia, eu, na, ru, cn]
# 参数2 location: 服务器的物理地址，本地测试随便填
python init/setup.py -r <region> -l <location>
```

### 运行代码

```bash
# 运行 API 服务
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug
```