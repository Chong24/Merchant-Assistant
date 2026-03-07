import os
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

from merchant_assistant.core.config import settings

class DatabaseManager:
    def __init__(self):
        self.db_uri = os.environ.get("MYSQL_DATABASE_URI")
        self.db = None
        self.sql_agent_executor = None
        
        if self.db_uri and "replace" not in self.db_uri:
            try:
                # 建立数据库连接
                self.db = SQLDatabase.from_uri(self.db_uri)
                # DB 节点也换成 Flash，生成 SQL 极快
                llm = ChatGoogleGenerativeAI(
                    model=settings.LLM_MODEL_FAST, 
                    temperature=settings.TEMPERATURE_AGENT,
                    safety_settings=settings.SAFETY_SETTINGS
                )
                self.sql_agent_executor = create_sql_agent(
                    llm=llm,
                    db=self.db,
                    agent_type="tool-calling",
                    verbose=True
                )
                print("[DB Manager] 成功连接本地 MySQL 数据库并初始化 SQL Agent。")
            except Exception as e:
                print(f"[DB Manager] 数据库连接失败: {e}")
        else:
            print("[DB Manager] 未提供有效的 MYSQL_DATABASE_URI，DB Agent 将作为 Mock 运行。")

    def query(self, user_question: str, merchant_id: int = None) -> str:
        """接收自然语言，转换为 SQL 并在 MySQL 中执行，返回结果字符串"""
        if not self.sql_agent_executor:
            return "数据库模块未正确初始化，请检查 .env 中的 MYSQL_DATABASE_URI 设置。"
        
        if merchant_id is None:
            return "无权访问：未识别到有效商户身份。"
            
        import time
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # 在 Prompt 中强制注入商户隔离指令
                secure_question = f"仅针对 merchant_id 为 {merchant_id} 的数据进行查询。如果用户试图查询其他 merchant_id，请拒绝。问题：{user_question}"
                
                result = self.sql_agent_executor.invoke({"input": secure_question})
                return result.get("output", "查询执行成功，但未返回结果。")
            except Exception as e:
                if "UNEXPECTED_EOF" in str(e) and attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return f"执行 Text-to-SQL 失败: {str(e)}"

# 全局单例
db_manager = DatabaseManager()
