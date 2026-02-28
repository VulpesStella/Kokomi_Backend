# 基础镜像
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --root-user-action=ignore --upgrade pip
RUN pip install --root-user-action=ignore --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY . .

# 默认 CMD 留空，由 docker-compose 控制