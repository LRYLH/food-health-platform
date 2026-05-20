import asyncio
import os
import json
import re
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from modelscope import snapshot_download
from pymilvus import Collection, connections
# LlamaIndex 核心组件
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.milvus import MilvusVectorStore
from dashscope import Generation
from http import HTTPStatus

load_dotenv()
QWEN_MAX_MODEL = "qwen-max"

retriever = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever
    print("正在初始化算法，请稍候...")
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("警告：未检测到 DASHSCOPE_API_KEY！请检查 .env 文件。")
    milvus_uri = os.getenv("MILVUS_URI", "http://milvus:19530")
    print(f"DEBUG: 正在尝试连接 Milvus: {milvus_uri}")
    
    # 显式连接并检查
    try:
        connections.connect(uri=milvus_uri)
        collection = Collection("food_health_standards")
        collection.load()
        print(f"DEBUG: 成功加载集合，当前记录数: {collection.num_entities}")
    except Exception as e:
        print(f"DEBUG: 警告！无法加载集合 (如果这是第一次启动则忽略): {e}")

    max_retries = 5
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            print("准备拉取 BGE 模型...")
            local_model_path = snapshot_download(
                'AI-ModelScope/bge-small-zh-v1.5', 
                cache_dir='/tmp/local_models'
            )
            print(f"模型下载成功，位置: {local_model_path}")
            Settings.embed_model = HuggingFaceEmbedding(model_name=local_model_path)
            milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
            vector_store = MilvusVectorStore(
                uri=milvus_uri,
                collection_name="food_health_standards",
                dim=512
            )

            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            retriever = index.as_retriever(similarity_top_k=3)
            print("算法引擎初始化完成！文件读写通道已就绪。")
            break
        except Exception as e:
            print(f"算法引擎初始化失败 (第 {attempt}/{max_retries} 次): {e}")
            if attempt < max_retries:
                print(f"将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)
            else:
                print("已达到最大重试次数，算法引擎将不可用。")

    yield
    print("算法引擎已关闭。")

app = FastAPI(title="多模态 RAG 文件交互算法引擎", lifespan=lifespan)

# 用于反序列化和校验本地 rag_input 文件的结构
class RagAnalysisRequest(BaseModel):
    schema_version: str
    task_id: str
    voice_query: Optional[str] = None
    user_profile: Dict[str, Any] = {}
    vision: Dict[str, Any] = {}
    retrieval: Optional[Dict[str, Any]] = None
    output_requirements: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None

# HTTP 请求现在只接收一个极其轻量的 task_id 作为触发信号
class TaskTriggerRequest(BaseModel):
    task_id: str

@app.post("/api/ask")
async def ask_question(trigger: TaskTriggerRequest):
    if retriever is None:
        raise HTTPException(status_code=500, detail="算法大脑未准备就绪。")
        
    task_id = trigger.task_id
    
    # 读取 rag_input，写入 rag_output
    base_io_dir = "/app/model_io" if os.path.exists("/app/model_io") else "model_io"
    input_file_path = os.path.join(base_io_dir, "rag_input", f"{task_id}.json")
    output_dir = os.path.join(base_io_dir, "rag_output")
    output_file_path = os.path.join(output_dir, f"{task_id}.json")
    
    os.makedirs(output_dir, exist_ok=True)

    #  尝试读取后端写好的文件
    if not os.path.exists(input_file_path):
        raise HTTPException(status_code=404, detail=f"未找到输入文件: {input_file_path}")
        
    try:
        with open(input_file_path, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        
        request = RagAnalysisRequest(**file_data)
        
        # 提取核心查询词进行检索
        search_query = request.voice_query or ""
        food_name = request.vision.get("food_name", "该食品")
        ingredients = request.vision.get("ingredients", {}).get("raw_text", "")
        
        if not search_query:
            search_query = f"{food_name} {ingredients}"

        retrieved_nodes = retriever.retrieve(search_query)
        knowledge_base_str = "\n\n".join([node.node.text for node in retrieved_nodes])

        # 动态计算真实的检索置信度 
        node_scores = [node.score for node in retrieved_nodes if node.score is not None]

        real_retrieval_score = sum(node_scores) / len(node_scores) if node_scores else 0.1

        real_vision_score = request.vision.get("meta", {}).get("quality_score", 0.8)

        real_overall_score = (real_retrieval_score + real_vision_score) / 2

        allergens = ", ".join(request.user_profile.get("allergens", [])) or "无"
        diseases = ", ".join(request.user_profile.get("chronic_diseases", [])) or "无"

        # 组装 Prompt 调用大模型
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
        llm_response = Generation.call(
            model=QWEN_MAX_MODEL,
            prompt=final_prompt,
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        )
        if llm_response.status_code != HTTPStatus.OK:
            raise ValueError(f"通义千问 API 调用失败: code={llm_response.code} message={llm_response.message}")
        raw_text = llm_response.output.text.strip()

        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"大模型未能输出有效的 JSON。原始输出：{raw_text}")
            
        parsed_llm_json = json.loads(match.group(0))

        # 组装 RagAnalysisResponse
        final_response = {
            "schema_version": "1.0",
            "task_id": task_id,
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
                "overall": round(real_overall_score, 4),
                "vision": round(real_vision_score, 4),
                "retrieval": round(real_retrieval_score, 4)
            },
            "meta": {
                "rag_model": "qwen-max",
                "retriever": "llamaindex+milvus"
            }
        }

        # 将结果写入 rag_output 文件夹
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(final_response, f, ensure_ascii=False, indent=2)

        return final_response

    except Exception as e:
        print(f"RAG 处理失败: {e}")
        # 如果出错了，把错误信息写成 JSON 放进文件夹
        error_response = {
            "schema_version": "1.0",
            "task_id": task_id,
            "status": "failed",
            "risk_level": "UNKNOWN",
            "answer": "",
            "reference": [],
            "error": {
                "code": "RAG_PROCESSING_ERROR",
                "message": str(e)
            }
        }
        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(error_response, f, ensure_ascii=False, indent=2)
        except Exception as write_err:
            print(f"写入错误文件失败: {write_err}")
            
        return error_response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ALGO_SERVER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)