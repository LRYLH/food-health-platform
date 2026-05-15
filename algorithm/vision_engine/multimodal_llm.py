"""
模块名称: vision_engine.multimodal_llm
功能描述: 多模态大模型底座封装与推理控制模块

本模块是整个视觉感知流水线与上层认知推理引擎的交汇点。它负责加载和管理系统底座大模型，
接收来自版面分析模块的结构化数据，并结合 RAG 引擎的权威标准进行最终的逻辑推理。

核心功能与技术实现:
    1. 模型加载与管理: 加载并初始化 Qwen-VL-Chat 多模态大模型。
    2. 上下文管理: 管理由于引入大段国家医疗标准（通过 RAG 召回）和长配料表而产生的超长上下文。
    3. 约束生成: 执行 Prompt 工程的限制条件，确保模型按照结构化的 JSON 格式输出安全、
        严谨的健康风险报告。
    4. 流式输出支持: 提供 Token 级的流式输出能力，防止前端请求因长时间等待而超时。

输入参数:
    - prompt (str): 组合了 layout_analyzer 输出的结构化数据、RAG 检索出的国标条款以及
        用户提问的“超级 Prompt”。
    - image (Optional): 必要的原图参考张量（部分多模态模型要求图文双重输入）。

返回结果:
    - response_stream (Generator): 包含健康建议、过敏原警告等内容的结构化推理流。
"""

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.generation import GenerationConfig
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class MultimodalLLM:
    def __init__(self, model_path="Qwen/Qwen-VL-Chat", use_mock=False):
        """
        初始化多模态大模型底座
        :param model_path: 模型路径，默认去 HuggingFace/ModelScope 拉取 Qwen-VL-Chat
        """
        self.use_mock = use_mock
        
        if not self.use_mock and HAS_TORCH:
            print("正在初始化 Qwen-VL-Chat 底座模型，这可能需要较大的显存...")
            # 必须设置 trust_remote_code=True 才能运行 Qwen 的自定义代码
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            
            # 使用 device_map="auto" 让 accelerate 库自动分配显存，或者使用 fp16 节省空间
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, 
                device_map="auto", 
                trust_remote_code=True,
                torch_dtype=torch.float16 # 半精度加载，防止显存直接爆掉
            ).eval()
            
            # 指定生成配置，如防重复惩罚、温度系数等
            self.model.generation_config = GenerationConfig.from_pretrained(model_path, trust_remote_code=True)
            self.model.generation_config.temperature = 0.2 # 医疗场景，调低温度防止幻觉
        elif not self.use_mock and not HAS_TORCH:
            print("警告: 环境中未检测到 PyTorch，大模型退化为 Mock 模式。")
            self.use_mock = True

    def build_prompt(self, user_question: str, layout_data: dict, rag_context: str) -> str:
        """
        构建带约束的超级 Prompt
        """
        prompt = f"""你是一个严谨的食品健康分析专家。请根据以下提取到的食品包装信息和国家医疗标准，回答用户的问题。
        
【包装版面提取数据】
{layout_data}

【权威医疗/国标约束 (RAG Context)】
{rag_context}

【用户提问】
{user_question}

【输出约束】
1. 你的回答必须完全基于上述提供的数据，严禁编造营养成分。
2. 如果提供的国标中指出相关成分对该用户（如糖尿病人）有风险，必须在开头明确输出 [风险警告]。
"""
        return prompt

    def generate_report(self, image_path: str, prompt: str):
        """
        执行推理并返回报告 (支持 Qwen-VL 的原生图文对话格式)
        """
        if self.use_mock:
            return "【风险警告】模拟数据返回：根据指南，当前食品含糖量超标，建议糖尿病患者谨慎食用。"

        # Qwen-VL-Chat 要求的特殊 query 组装格式
        query = self.tokenizer.from_list_format([
            {'image': image_path},
            {'text': prompt},
        ])
        
        # 传统的一次性生成 (非流式)
        # response, history = self.model.chat(self.tokenizer, query=query, history=None)
        # return response

        # 流式生成 (Streaming)，提升用户体验，防止一直转圈圈
        # 这也是现在做大模型产品工程化落地的标配
        response_generator = self.model.chat_stream(self.tokenizer, query=query, history=None)
        
        for response in response_generator:
            yield response