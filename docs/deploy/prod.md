# 生产环境部署步骤

> 适用于 Windows/Linux 环境

通过 Docker 部署完整的生产环境

## 项目配置

复制一份文件 `env.example` 并重命名为 `env.pord`

```bash
# Linux:

# 复制模板文件
cp env.example env.prod
# 使用 vim 编辑配置
vim env.prod

# vim 指令
# i   - 进去 INSERT 模式
# Esc - 退出 INSERT 模式
# :wq - 写入文件并退出
```

> 仅需配置带 ★ 的配置项即可

```conf
PLATFORM="KokomiAPI-01"    # 标识符
LOG_LEVEL="debug"          # ★ log 输出级别
DEV_MODE=0                 # ★

API_ROOT_TOKEN="root"      # ★ 默认 Root 用户的 Token
API_USER_TOKEN="user"      # ★ 默认 User 用户的 Token

SQLITE_DIR=""              # 不填则按默认路径

MYSQL_HOST="mysql"
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=""     # ★ 
MYSQL_USER=""              # ★ 也可都填root及root密码
MYSQL_PASSWORD=""          # ★ 
MYSQL_DATABASE="wows"

REDIS_HOST="redis"
REDIS_PORT=6379
REDIS_PASSWORD=""          # ★ 
REDIS_DATABASE=0

RABBITMQ_HOST="rabbitmq"
RABBITMQ_DEFAULT_USER=""   # ★ 
RABBITMQ_DEFAULT_PASS=""   # ★ 
```

## 初始化

```bash
# 执行项目初始化脚本
# 参数1 region: 可选值 [asia, eu, na, ru, cn]
# 参数2 location: 服务器的物理地址，本地测试随便填
python init/setup.py -r <region> -l <location>
```

```bash
# 部署相关服务
docker compose up -d mysql
docker compose up -d redis
docker compose up -d rabbitmq
```

```bash
# 执行数据库初始化脚本
python init/rebuild_db.py

# 写入船只基本数据
python init/insert_ship.py

# 写入工会数据（需自行准备）
python init/insert_clan.py -c 0

# 写入用户数据（需自行准备）
python init/insert_user.py -c 0
```

```bash
docker compose up -d season
docker compose up -d member
docker compose up -d account
docker compose up -d cache
docker compose up -d stats
docker compose up -d recent
```