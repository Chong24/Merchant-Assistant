import os
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

def inspect_chroma():
    persist_directory = "./merchant_assistant/db_storage/chroma"
    if not os.path.exists(persist_directory):
        print(f"错误: 目录 {persist_directory} 不存在。")
        return

    # 初始化嵌入模型
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    
    # 加载向量库
    vector_store = Chroma(
        collection_name="merchant_kb",
        embedding_function=embeddings,
        persist_directory=persist_directory
    )

    # 获取所有数据
    data = vector_store.get()
    ids = data['ids']
    metadatas = data['metadatas']
    documents = data['documents']

    print(f"\n=== 向量知识库概览 ({len(ids)} 条记录) ===")
    
    if not ids:
        print("知识库目前为空。")
        return

    # 打印前 5 条作为样例
    for i in range(min(5, len(ids))):
        print(f"\n[ID]: {ids[i]}")
        print(f"[元数据]: {metadatas[i]}")
        print(f"[内容预览]: {documents[i][:200]}...")
    
    if len(ids) > 5:
        print(f"\n... 还有 {len(ids) - 5} 条记录未展示。")

if __name__ == "__main__":
    inspect_chroma()
