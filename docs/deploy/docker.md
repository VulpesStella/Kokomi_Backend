# Docker 安装

```bash
# 安装依赖
sudo apt update && sudo apt install -y ca-certificates curl

# 添加 Docker GPG 密钥和官方源
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update

# 安装 Docker 核心组件
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 验证安装
sudo docker version

# （可选）将当前用户加入 docker 组，免 sudo
sudo usermod -aG docker $USER
# 需重新登录生效