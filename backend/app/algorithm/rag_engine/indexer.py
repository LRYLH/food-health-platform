import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import nest_asyncio
from dotenv import load_dotenv

# LlamaIndex 核心组件
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_parse import LlamaParse

# 允许在 Jupyter 或异步环境中运行 LlamaParse
nest_asyncio.apply()

def main():
    print("启动数据知识库构建流程...")
    
    # 1. 加载 .env 文件中的环境变量
    load_dotenv()
    # 获取当前脚本 indexer.py 所在目录 (rag_engine) 的上一级目录 (algorithm)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 精确指向 algorithm/data 下的文件夹
    standards_dir = os.path.join(base_dir, "data", "standards")
    hard_samples_dir = os.path.join(base_dir, "data", "hard_samples")
    parsed_mds_dir = os.path.join(base_dir, "data", "parsed_mds") # 顺便创建个放 md 结果的文件夹
    
    # 自动创建所需目录（防崩溃护城河）
    os.makedirs(standards_dir, exist_ok=True)
    os.makedirs(hard_samples_dir, exist_ok=True)
    os.makedirs(parsed_mds_dir, exist_ok=True)
    
    # 检查文件夹里有没有文件
    has_standards = len(os.listdir(standards_dir)) > 0
    has_hard_samples = len(os.listdir(hard_samples_dir)) > 0
    
    if not has_standards and not has_hard_samples:
        print(f"数据文件夹为空,请将 PDF 放入以下路径：\n{standards_dir}\n或\n{hard_samples_dir}")
        return
    # =======================================================================
    
    # 2. 配置全局 Embedding 模型
    print("正在加载 BGE 中文向量模型 (首次运行会自动下载)...")
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)

    all_docs = []

    # 3. 解析第一梯队：纯文本 PDF (standards)
    if has_standards:
        print(f"正在解析纯文本规范 ({standards_dir})...")
        text_docs = SimpleDirectoryReader(standards_dir).load_data()
        print(f"纯文本解析完成，共获取 {len(text_docs)} 个文档片段。")
        all_docs.extend(text_docs)

    # 4. 解析第二、三梯队：复杂表格 PDF (hard_samples)
    if has_hard_samples:
        print(f"正在调用 LlamaParse 解析复杂表格数据 ({hard_samples_dir})...")
        parser = LlamaParse(
            api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
            result_type="markdown",
            language="ch_sim"
        )
        file_extractor = {".pdf": parser}
        table_docs = SimpleDirectoryReader(
            hard_samples_dir, 
            file_extractor=file_extractor
        ).load_data()
        print(f"复杂表格解析完成，共获取 {len(table_docs)} 个文档片段。")
        all_docs.extend(table_docs)

    if not all_docs:
        print("没有读取到任何文档，程序退出。")
        return

    # 5. 连接 Milvus 向量数据库并写入数据
    milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
    print(f"正在连接 Milvus 数据库: {milvus_uri}")
    
    vector_store = MilvusVectorStore(
        uri=milvus_uri,
        collection_name="food_health_standards",
        dim=512,
        overwrite=True
    )

    # 6. 生成向量并存入数据库
    print("正在进行文本切块、向量化计算，并写入 Milvus... 请耐心等待！")
    index = VectorStoreIndex.from_documents(
        all_docs,
        vector_store=vector_store,
        show_progress=True
    )

    print("所有国标数据已成功注入向量！")

if __name__ == "__main__":
    main()