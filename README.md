##基于多模态大模型的食品信息智能分析与健康辅助平台
$Bridging the Semantic Gap in Food Safety via Multi-modal LLM$

###1. 项目愿景
在当前的食品消费市场中，存在着显著的供需错配现象。复杂的配料表、晦涩的化学名词以及微小的排版，在银发族、视障人士、过敏体质者与食品安全之间划下了一道深深的信息鸿沟。

本项目致力于构建“视觉-文本-知识”三位一体的智能体，通过多模态感知剥离物理干扰，并依托 Authority RAG 技术强制引入医学指南与国家标准进行交叉核查。我们的最终目标是提供“拍照即扫，开口即懂”的无障碍体验，让科技真正俯身服务于每一个脆弱的个体。

###2. 系统架构与核心技术
系统采用端云协同的微服务生态，通过解耦设计保障高可用性与算力资源的弹性分配。

跨端交互层：基于 Uni-app 与 Vue 3 构建。专注于无障碍体验设计，实现流式语音唤醒与端侧轻量级图像采集。

异步网关层：基于 FastAPI 与 Celery 构建。作为流量中枢，通过 RabbitMQ 消息队列对高耗时的多模态推理任务进行削峰填谷。

视觉感知管线：结合 OpenCV 与 LayoutLMv3 模型。有效解决真实超市货架环境下的反光、褶皱等物理干扰，精准提取食品包装的空间逻辑坐标。

权威推理引擎：以 Qwen-VL-Chat 为底座，基于 LlamaIndex 框架接入 Milvus 向量数据库。动态检索《中国糖尿病医学营养治疗指南》及相关食品国标，抑制模型幻觉，确保输出结论的医疗级严谨性。

###3. 目录结构
本仓库采用单一代码库（Monorepo）模式组织微服务模块：

frontend/：跨端应用源码及无障碍组件库

backend/：业务网关、关系型数据模型与异步调度节点

algorithm/：视觉感知管线、RAG 检索引擎与 gRPC 服务端

docker/：全局基础设施（PostgreSQL, Redis, Milvus, MinIO）的容器编排脚本

docs/：API 契约文档、知识库构建规范与学术综述材料

data/：脱敏后的校内困难样本采集集（不包含至版本控制）

###4. 本地快速启动
环境依赖：需预先安装 Docker 与 Docker Compose，且运行算法节点需配置 NVIDIA Container Toolkit 支持 GPU 加速。

第一步：克隆代码仓库
git clone https://github.com/YourOrg/food-health-platform.git
cd food-health-platform

第二步：环境配置
复制环境变量模板并填入相应的密钥与配置：
cp docker/.env.example docker/.env

第三步：一键拉起基础设施与业务后端
cd docker
docker-compose up -d postgres redis minio milvus api_gateway celery_worker

第四步：启动独立算法节点
算法节点由于高度依赖 GPU 显存，需单独挂载模型权重目录后启动：
docker-compose -f docker-compose.algo.yml up -d

###5. 研发团队与致谢
项目负责人：刘昊

核心开发团队：蒲今、徐黄浩、巨文博、刘昊

指导教师：蒋智威（助理研究员）

申报单位：智能软件与工程学院 
