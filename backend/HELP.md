# 开发环境说明

## 一键启动

```bash
# 首次或依赖变更时（需要几分钟，仅第一次慢）
docker compose up -d --build

# 之后日常启动
docker compose up -d
```

## 环境组成

| 服务 | 地址 | 说明 |
|------|------|------|
| FastAPI 应用 | `localhost:8000` | 代码挂载，保存即生效 |
| API 文档 | `localhost:8000/docs` | Swagger UI |
| MySQL | `localhost:3307` | 数据持久化在 `./mysql-data/` |
| Redis | `localhost:6379` | 数据持久化在 `./redis-data/` |

## 前置条件

```bash
# 1. 确保 .env 文件存在并填写必要配置
cp .env.example .env   # 然后编辑 .env

# 2. 确保已安装 Docker Desktop
docker --version
```

## 常用命令

```bash
docker compose ps              # 查看运行状态
docker compose logs -f app     # 查看应用日志
docker compose exec app bash   # 进入容器调试
docker compose down            # 停止并移除容器
docker compose down -v         # 停止并清除数据库数据
```

## 改动后需要重建的情况

- 修改了 `requirements.txt`（新增/删除 pip 包）
- 修改了 `Dockerfile`（系统依赖变更）

```bash
docker compose up -d --build
```

日常修改业务代码无需重建，保存后自动热重载。
