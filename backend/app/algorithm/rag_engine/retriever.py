import os
import json
import re
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# LlamaIndex 核心组件
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.llms.dashscope import DashScope, DashScopeGenerationModels

load_dotenv()

# 全局变量，用于在 lifespan 中初始化
retriever = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever
    print("正在初始化算法，请稍候...")
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("警告：未检测到 DASHSCOPE_API_KEY，通义千问大模型将无法调用！请检查 .env 文件。")
        
    try:
        # 1. 挂载模型
        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")
        Settings.llm = DashScope(
            model_name=DashScopeGenerationModels.QWEN_MAX,
            api_key=os.getenv("DASHSCOPE_API_KEY", "missing_key") 
        )

        # 2. 连接 Milvus
        milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
        vector_store = MilvusVectorStore(
            uri=milvus_uri,
            collection_name="food_health_standards",
            dim=512
        )

        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        retriever = index.as_retriever(similarity_top_k=3)
        print("算法引擎初始化完成！Milvus 和大模型已就绪。")
        
    except Exception as e:
        print(f"❌ 算法引擎初始化失败 (请检查 Milvus 是否启动): {e}")
        # 这里不抛出异常，允许 FastAPI 启动，但后续请求会报错，方便排查
        
    yield  # 此时应用开始接收 HTTP 请求
    
    print("🛑 算法引擎已关闭。")

# 将 lifespan 绑定到 app
app = FastAPI(title="多模态 RAG 算法服务引擎 API", lifespan=lifespan)

class RagAnalysisRequest(BaseModel):
    schema_version: str
    task_id: str
    voice_query: Optional[str] = None
    user_profile: Dict[str, Any] = {}
    vision: Dict[str, Any] = {}
    retrieval: Optional[Dict[str, Any]] = None
    output_requirements: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None

@app.post("/api/ask")
async def ask_question(request: RagAnalysisRequest):
    # 拦截：如果 retriever 初始化失败，直接返回 500
    if retriever is None:
        raise HTTPException(status_code=500, detail="算法大脑未准备就绪 (Milvus 连接失败或模型未加载)。请查看算法容器日志。")
        
    try:
        search_query = request.voice_query or ""
        food_name = request.vision.get("food_name", "该食品")
        ingredients = request.vision.get("ingredients", {}).get("raw_text", "")
        
        if not search_query:
            search_query = f"{food_name} {ingredients}"

        retrieved_nodes = retriever.retrieve(search_query)
        knowledge_base_str = "\n\n".join([node.node.text for node in retrieved_nodes])

        allergens = ", ".join(request.user_profile.get("allergens", [])) or "无"
        diseases = ", ".join(request.user_profile.get("chronic_diseases", [])) or "无"

        final_prompt = f"""
你是一个严谨的食品安全与医学健康分析专家。请根据以下信息分析食品对用户的健康风险。

【背景知识：检索到的国家标准与医学指南】
{knowledge_base_str}

【用户健康画像】
过敏史：{allergens}
慢性疾病：{diseases}

【视觉模型识别到的食品数据】
食品名称：{food_name}
配料表：{ingredients}
营养成分：{json.dumps(request.vision.get('nutrition_facts', {}), ensure_ascii=False)}

【用户的提问】
{request.voice_query or "用户未提出具体问题，请综合评估该食品是否适合该用户食用。"}

请严格综合分析，并【必须】以如下 JSON 格式输出你的结论。不要输出任何 Markdown 标记（如 ```json），不要有任何前言后语，直接输出纯 JSON 对象：
{{
  "risk_level": "HIGH", // 必须是 HIGH, MEDIUM, LOW, 或 UNKNOWN 之一
  "answer": "直接回答用户的问题，并给出核心结论...",
  "health_advice": "一段简短的健康饮食建议...",
  "warnings": [
    {{"type": "allergen", "level": "HIGH", "message": "发现花生配料，可能触发过敏"}}
  ],
  "suggestions": ["建议一", "建议二"]
}}
"""
        response = Settings.llm.complete(final_prompt)
        raw_text = str(response).strip()

        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"大模型未能输出有效的 JSON。原始输出：{raw_text}")
            
        parsed_llm_json = json.loads(match.group(0))

        return {
            "schema_version": "1.0",
            "task_id": request.task_id,
            "status": "completed",
            "food_name": food_name,
            "risk_level": parsed_llm_json.get("risk_level", "UNKNOWN"),
            "answer": parsed_llm_json.get("answer", "分析完成。"),
            "health_advice": parsed_llm_json.get("health_advice", ""),
            "warnings": parsed_llm_json.get("warnings", []),
            "suggestions": parsed_llm_json.get("suggestions", []),
            "reference": [node.node.text[:200] + "..." for node in retrieved_nodes],
            "citations": [],
            "confidence": {
                "overall": 0.8,
                "vision": request.vision.get("meta", {}).get("quality_score", 0.8),
                "retrieval": 0.85
            },
            "meta": {
                "rag_model": "qwen-max",
                "retriever": "llamaindex+milvus",
            }
        }

    except Exception as e:
        print(f"RAG 处理失败: {e}")
        return {
            "schema_version": "1.0",
            "task_id": getattr(request, "task_id", "unknown_task_id"),
            "status": "failed",
            "risk_level": "UNKNOWN",
            "answer": "",
            "reference": [],
            "error": {
                "code": "RAG_PROCESSING_ERROR",
                "message": str(e)
            }
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ALGO_SERVER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)