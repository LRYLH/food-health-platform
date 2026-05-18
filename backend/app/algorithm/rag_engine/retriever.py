import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# LlamaIndex 核心组件
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.llms.dashscope import DashScope, DashScopeGenerationModels

load_dotenv()

app = FastAPI(title="多模态 RAG 算法服务引擎 API")

print("正在初始化算法大脑，请稍候...")

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
Settings.llm = DashScope(
    model_name=DashScopeGenerationModels.QWEN_MAX,
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
vector_store = MilvusVectorStore(
    uri=milvus_uri,
    collection_name="food_health_standards",
    dim=512
)

index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

# 【核心改动 1】我们不再使用傻瓜式的 query_engine，而是把它降级为单纯的“检索器”
retriever = index.as_retriever(similarity_top_k=3)

print("算法引擎初始化完成！")

# 【核心改动 2】扩展请求模型，接收主后端传来的额外数据
class QueryRequest(BaseModel):
    question: str
    report_data: Optional[str] = None  # 这是主后端发来的，比如 OCR 识别出的配料表或体检数据

@app.post("/api/ask")
async def ask_question(request: QueryRequest):
    try:
        # 第一步：只用用户的“提问”去 Milvus 数据库里捞国标（保证向量检索的精准度）
        retrieved_nodes = retriever.retrieve(request.question)
        
        # 将捞出来的国标片段拼接成字符串
        knowledge_base_str = "\n\n".join([node.node.text for node in retrieved_nodes])
        
        # 处理主后端传来的表格数据
        user_table_str = request.report_data if request.report_data else "用户未提供额外的图表数据。"

        # 第二步：构建给通义千问的“三明治”超级 Prompt
        final_prompt = f"""
你是一个严谨的食品安全与医学健康分析专家。请根据以下提供的信息回答用户的问题。

【背景知识：检索到的国家标准与医学指南】
{knowledge_base_str}

【用户当前数据：识别出的配料表、检测报告等】
{user_table_str}

【用户的提问】
{request.question}

请务必结合上述“背景知识”和“用户当前数据”进行综合分析。如果数据中存在违规或超标现象，请明确指出。
"""
        
        # 第三步：直接调用大模型进行推理生成
        response = Settings.llm.complete(final_prompt)
        
        return {
            "answer": str(response),
            "reference_sources": [node.node.text[:200] + "..." for node in retrieved_nodes]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ALGO_SERVER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)