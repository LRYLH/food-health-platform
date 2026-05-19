# 环境初始化帮助文档

本文档面向一台全新（未安装任何开发环境）的 Windows 电脑，按步骤操作即可将整个后端服务跑起来。

---

## 1. 安装 Docker Desktop

Docker 负责运行 MySQL、Redis、Milvus 等服务，无需手动安装这些中间件。

1. 打开 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 下载并安装，安装完成后**重启电脑**
3. 重启后 Docker Desktop 会自动启动，任务栏出现鲸鱼图标即为运行中

> **注意**：如果遇到 "WSL 2 required" 提示，按引导安装 WSL 2 即可。如果安装 WSL 2 遇到网络问题，可以用管理员身份打开 PowerShell 运行 `wsl --update --web-download` 走网页下载。

验证安装：

```bash
docker --version
docker compose version
```

---

## 2. 克隆项目并进入后端目录

```bash
git clone https://github.com/LRYLH/food-health-platform.git
cd food-health-platform/backend
```

---

## 3. 创建 .env 配置文件

项目默认不包含 `.env`（已在 `.gitignore` 中排除），需要手动创建：

```bash
copy .env.example .env
```

然后编辑 `.env` 文件，填入以下**必填项**：

```ini
# MySQL root 密码（自定义）
MYSQL_ROOT_PASSWORD=your_mysql_password

# JWT 签名密钥（随便填一串随机字符即可）
SECRET_KEY=your_random_secret_key

# 阿里百炼 API Key（必填，用于通义千问大模型调用）
# 免费获取：https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx

# LlamaCloud API Key（必填，用于 PDF 表格解析入库）
# 免费获取：https://cloud.llamaindex.ai/
LLAMA_CLOUD_API_KEY=llx-xxxxxxxxxxxxxxxx

# 百度 OCR API Key（必填，用于图片文字识别）
# 免费获取：https://console.bce.baidu.com/ai/#/ai/ocr/overview/index
BAIDU_OCR_API_KEY=xxxxxxxxxxxxxxxx
BAIDU_OCR_SECRET_KEY=xxxxxxxxxxxxxxxx
```

其余配置项使用默认值即可。

---

## 4. 构建镜像并启动全部服务

```bash
docker compose up -d --build
```

首次执行会下载基础镜像并安装 Python 依赖（使用清华镜像源），耗时 5~10 分钟。

启动后会依次拉起以下容器：

| 容器 | 端口 | 用途 |
|------|:---:|------|
| food_health_mysql | 3307 | 关系型数据库 |
| food_health_redis | 6379 | 缓存 |
| food_health_etcd | 2379 | Milvus 元数据存储 |
| food_health_minio | 9000-9001 | Milvus 对象存储 |
| food_health_milvus | 19530 | 向量数据库 |
| food_health_algo | 8001 | RAG 算法引擎 |
| food_health_app | 8000 | FastAPI 业务后端 |

检查所有容器状态：

```bash
docker compose ps
```

确保 STATUS 列全部为 `Up`（或 `Up ... (healthy)`），没有 `restarting` 或 `exited`。

---

## 5. 初始化知识库（写入 Milvus 向量库）

容器启动后，Milvus 中的知识库集合为空，需要将国标 PDF 文档做向量化入库。

### 5.1 放入知识文档

将 PDF 文档放入以下目录：

```
backend/app/algorithm/data/standards/       ← 纯文本/简单表格 PDF
backend/app/algorithm/data/hard_samples/    ← 复杂表格 PDF（走 LlamaParse）
```

> 这两个目录已自动创建，只需放入文件。

### 5.2 运行索引脚本

```bash
docker exec food_health_algo python app/algorithm/rag_engine/indexer.py
```

执行过程中会：
1. 下载 BGE 中文向量模型（首次约 1 分钟，缓存在 `hf-cache/` 目录）
2. 解析 PDF 文档
3. 文本切块并向量化
4. 写入 Milvus `food_health_standards` 集合

看到 `所有国标数据已成功注入向量！` 即为完成。

---

## 6. 验证

```bash
# 检查后端健康状态
curl http://127.0.0.1:8000/health

# 应返回
# {"status":"ok","environment":"development"}
```

也可以打开浏览器访问 `http://127.0.0.1:8000/docs` 查看 Swagger API 文档。

---

## 7. 日常使用

```bash
docker compose ps                  # 查看运行状态
docker compose logs -f app         # 查看应用日志
docker compose down                # 停止所有服务
docker compose up -d               # 重新启动（无需 --build）
docker compose up -d --build       # 依赖变更后重建镜像
docker restart food_health_algo    # 单独重启算法引擎
```

---

## 8. 常见问题

### Q: Docker Desktop 启动报错 "WSL 2 is not installed"

以管理员身份打开 PowerShell 执行：

```powershell
wsl --install -d Ubuntu
wsl --update --web-download
```

### Q: 构建镜像时 `pip install` 失败或下载很慢

Dockerfile 中已配置清华 PyPI 镜像源。如果仍然失败，可能是 Docker 网络问题，尝试在 Docker Desktop 设置中将 DNS 改为 `8.8.8.8`。

### Q: 启动后 `food_health_algo` 返回 500 错误

Milvus 启动较慢导致 algo 初始化时连接失败。项目已内置重试机制（启动时最多重试 5 次 × 3 秒），如仍失败可手动重启：

```bash
docker restart food_health_algo
```

### Q: 提示 `DASHSCOPE_API_KEY` 无效

检查 `.env` 中的 Key 是否正确。阿里百炼新用户有 100 万 Token 免费额度。

### Q: 端口被占用（如 3307、8000）

关闭占用端口的程序，或修改 `.env` 中的端口配置。

```bash
# 查看端口占用
netstat -ano | findstr :3307
```

### Q: 数据会丢失吗

| 数据 | 持久化位置 | 说明 |
|------|------|------|
| MySQL | `mysql-data/` | `docker compose down` 不会删除，重新 `up` 即可恢复 |
| Redis | `redis-data/` | 同上 |
| Milvus | `milvus-data/` | 同上 |
| HF 模型 | `hf-cache/` | 同上，删除需重新下载模型 |

如需彻底清除所有数据重新开始：

```bash
docker compose down -v
rm -rf mysql-data redis-data milvus-data
```

### Q: 如何查看某个容器的实时日志

```bash
docker logs -f food_health_app         # 业务后端
docker logs -f food_health_algo        # 算法引擎
docker logs -f food_health_milvus      # 向量数据库
```

---

## 9. 前置端开发（可选）

前端项目在 `frontend/` 目录，使用 Uni-app + Vue 3。

```bash
cd frontend
npm install
npm run dev:h5
```

如需与本地后端联调，修改 `frontend/src/utils/request.ts` 中的 `BASE_URL` 指向 `http://127.0.0.1:8000`。

---

## 附录：API Key 获取指引

| Key | 平台 | 获取步骤 |
|-----|------|------|
| DASHSCOPE_API_KEY | 阿里云百炼 | [控制台](https://bailian.console.aliyun.com/) → 模型广场 → API-KEY 管理 → 创建 |
| LLAMA_CLOUD_API_KEY | LlamaCloud | [注册](https://cloud.llamaindex.ai/) → API Keys → Create |
| BAIDU_OCR_API_KEY | 百度智能云 | [控制台](https://console.bce.baidu.com/) → 文字识别 → 创建应用 → 获取 API Key / Secret Key |
