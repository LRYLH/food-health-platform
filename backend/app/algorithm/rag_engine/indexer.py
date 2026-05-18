import os
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
    
    # 1. 加载 .env 文件中的环境变量 (API Keys 和 Milvus 地址)
    load_dotenv()
    
    # 2. 配置全局 Embedding 模型 (把文字变成向量的引擎)
    # 这里我们使用 HuggingFace 上的开源轻量级中文模型 BGE
    print("正在加载 BGE 中文向量模型 (首次运行会自动下载)...")
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
    # 设置切块大小：每 512 个 token 切一刀
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)

    # 3. 解析第一梯队：纯文本 PDF
    print("正在解析纯文本规范 (pure_text/)...")
    text_docs = SimpleDirectoryReader("./pure_text").load_data()
    print(f"纯文本解析完成，共获取 {len(text_docs)} 个文档片段。")

    # 4. 解析第二、三梯队：复杂表格 PDF (调用 LlamaCloud 视觉解析)
    print("正在调用 LlamaParse 解析复杂表格数据 (complex_tables/)...")
    parser = LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type="markdown",  # 关键：把表格强制转为 Markdown 格式，防止大模型幻觉
        language="ch_sim"        # 提示解析器这是简体中文文档
    )
    # 将 LlamaParse 绑定到所有的 .pdf 文件上
    file_extractor = {".pdf": parser}
    table_docs = SimpleDirectoryReader(
        "./complex_tables", 
        file_extractor=file_extractor
    ).load_data()
    print(f"复杂表格解析完成，共获取 {len(table_docs)} 个文档片段。")

    # 合并所有文档
    all_docs = text_docs + table_docs

    # 5. 连接 Milvus 向量数据库并写入数据
    milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
    print(f"正在连接 Milvus 数据库: {milvus_uri}")
    
    vector_store = MilvusVectorStore(
        uri=milvus_uri,
        collection_name="food_health_standards",  # 你的集合(表)名称
        dim=512,                                  # BGE-small 的向量维度是 512
        overwrite=True                            # 每次运行脚本时清空旧数据，重新建库
    )

    # 6. 生成向量并存入数据库 (这一步最耗时)
    print("正在进行文本切块、向量化计算，并写入 Milvus... 请耐心等待！")
    index = VectorStoreIndex.from_documents(
        all_docs,
        vector_store=vector_store,
        show_progress=True
    )

    print("所有国标数据已成功注入向量库")

if __name__ == "__main__":
    main()