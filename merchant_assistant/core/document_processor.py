import os
from dotenv import load_dotenv
load_dotenv()

import shutil
from typing import List
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

VECTOR_DB_DIR = os.path.join(os.path.dirname(__file__), "../db_storage/chroma")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../uploads")

class KnowledgeBaseManager:
    def __init__(self):
        # 确保目录存在
        os.makedirs(VECTOR_DB_DIR, exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 初始化 Embedding 模型
        from merchant_assistant.core.config import settings
        self.embeddings = GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL)
        
        # 初始化或加载 Chroma 向量库
        self.vector_store = Chroma(
            collection_name="merchant_kb",
            embedding_function=self.embeddings,
            persist_directory=VECTOR_DB_DIR
        )

    def process_and_store_file(self, file_path: str) -> int:
        """
        加载文件、切片并入库，返回新增的块数量。
        """
        # 1. 根据扩展名选择解析器
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext in [".txt", ".md", ".csv"]:
            loader = TextLoader(file_path, encoding='utf-8')
        else:
            raise ValueError(f"暂不支持的文件格式: {ext}")
            
        documents = loader.load()
        
        # 2. 切分文档
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            add_start_index=True,
        )
        chunks = text_splitter.split_documents(documents)
        
        # 3. 向量化入库
        self.vector_store.add_documents(chunks)
        
        return len(chunks)

    def retrieve_with_confidence(self, query: str, top_k: int = 3):
        """
        检索前 K 个相关文本段并返回分数。
        Chroma 默认为距离得分（越小越相近），将距离转化为简单的假部署信度。
        """
        docs_and_scores = self.vector_store.similarity_search_with_score(query, k=top_k)
        if not docs_and_scores:
            return []
            
        results = []
        for doc, score in docs_and_scores:
            # 简单映射：距离越小，置信度越高；假设常见合理匹配的得分普遍小于 1.0。
            # distance: 0 -> conf: 100%, distance: 1 -> conf: 50%
            conf = max(0.0, 1.0 - (score / 2.0))
            results.append((doc, conf))
        return results

    def add_qa_pair(self, question: str, answer: str):
        content = f"问题: {question}\n答案: {answer}"
        doc = Document(page_content=content, metadata={"source": "数据飞轮(人工审核)", "type": "qa_pair"})
        self.vector_store.add_documents([doc])

# 全局单例
kb_manager = KnowledgeBaseManager()
