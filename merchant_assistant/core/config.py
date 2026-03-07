import os
from dotenv import load_dotenv

load_dotenv()

# 从环境变量读取，方便在 .env 中直接切换
# 如果未设置，默认使用 gemini-1.5-pro (因为 2.5 可能是实验性名称，不同区域支持不同)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")

class Settings:
    # 核心推理模型 (Router/Worker 使用 Flash 极速模型)
    LLM_MODEL_FAST = os.environ.get("GEMINI_MODEL_FAST", DEFAULT_MODEL)
    # 高级分析模型 (Summary 使用 Pro 高精度模型)
    LLM_MODEL_PRO = os.environ.get("GEMINI_MODEL_PRO", DEFAULT_MODEL)
    
    LLM_MODEL = LLM_MODEL_FAST
    
    # 向量化模型
    EMBEDDING_MODEL = "gemini-embedding-001"
    
    # 温度配置
    TEMPERATURE_ROUTER = 0
    TEMPERATURE_AGENT = 0
    TEMPERATURE_SUMMARY = 0.7

    # 安全设置：根据报错信息，当前 LangChain 或 Pydantic 版本要求必须是字典
    SAFETY_SETTINGS = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }

settings = Settings()
