# Docker 使用说明

使用 Docker 可以跳过所有环境搭建步骤，直接运行多机仿真。

---

## 前置条件

请确保你的系统已安装 Docker。

**Windows 用户**：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并在设置中启用 WSL2 后端。

**Ubuntu 用户**：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录后生效
```

---

## 构建镜像

```bash
cd docker
docker build -t drone-de-icing .
```

构建过程需要下载和编译 PX4，首次构建可能需要 30-60 分钟，后续会使用缓存。镜像大小约 5-8 GB。

---

## 运行仿真

### Linux / WSL2（WSLg 图形支持）

```bash
xhost +local:docker

# 两机仿真
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --name drone-sim \
  drone-de-icing \
  bash -c "./scripts/start_sim.sh"

# 在另一个终端连入容器运行控制脚本
docker exec -it drone-sim bash -c "./scripts/run_dual_takeoff.sh"
```

### 五机仿真

```bash
# 终端 A
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --name drone-sim \
  drone-de-icing \
  bash -c "./scripts/start_sim_5.sh"

# 终端 B
docker exec -it drone-sim bash -c "./scripts/run_five_ring_show.sh"
```

### 无 GUI 模式（服务器/CI 环境）

```bash
docker run -it --rm \
  --name drone-sim \
  drone-de-icing \
  bash -c "./scripts/start_sim.sh --headless"
```

---

## 交互式进入容器

如果你想在容器内自由操作（调试、修改代码等）：

```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  drone-de-icing \
  bash
```

进入后手动执行启动命令：

```bash
cd /root/catkin_ws/src/multi_uav
./scripts/start_sim_5.sh
```

---

## 开发模式（挂载本地代码）

如果你想在容器外修改代码，实时同步到容器内：

```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $(pwd)/scripts:/root/catkin_ws/src/multi_uav/scripts \
  drone-de-icing \
  bash
```

这样你在宿主机上修改 `scripts/` 目录下的文件，容器内会实时看到变化。

---

## 常见问题

### Q: Gazebo 窗口打不开

确认 X11 转发已设置：

```bash
# 宿主机上执行
xhost +local:docker

# 确认 DISPLAY 变量不为空
echo $DISPLAY
```

如果使用远程服务器，考虑用 VNC 或无 GUI 模式。

### Q: 构建失败

最常见的原因是网络问题导致 apt 或 git 下载失败。重新运行 `docker build` 会从断点继续（Docker 有层缓存）。

### Q: 容器内五机仿真很卡

Docker 默认内存限制可能不够。在 Docker Desktop 设置中，将内存分配调到至少 8GB（推荐 16GB）。
