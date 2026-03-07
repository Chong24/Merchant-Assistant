from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

from merchant_assistant.core.auth import (
    verify_password, get_password_hash, create_access_token, decode_access_token
)
from merchant_assistant.main import create_assistant_graph
from merchant_assistant.core.document_processor import kb_manager, UPLOAD_DIR
from merchant_assistant.core.qa_manager import qa_manager
from sqlalchemy import create_engine, text
from langchain_core.messages import HumanMessage

app = FastAPI(title="商户助手的多智能体 API")

# 必须添加 CORS，否则前端无法访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
engine = create_engine(os.environ.get("MYSQL_DATABASE_URI"))

# Pydantic Models
class UserRegister(BaseModel):
    username: str
    password: str
    merchant_name: str

class UserLogin(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

class QAApproveRequest(BaseModel):
    id: int
    question: str
    answer: str

# Auth Helpers
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的认证凭证或登录已过期")
    return payload

from fastapi.concurrency import run_in_threadpool # 用于异步调用同步阻塞库

@app.post("/register")
async def register(req: UserRegister):
    def do_register():
        with engine.connect() as conn:
            with conn.begin():
                # 1. 检查用户
                existing = conn.execute(
                    text("SELECT id FROM personnel WHERE username = :u"), 
                    {"u": req.username}
                ).fetchone()
                if existing:
                    raise HTTPException(status_code=400, detail="该用户名已存在")

                # 2. 创建商户
                merchant_no = f"M{datetime.now().strftime('%Y%m%d%H%M%S')}"
                res = conn.execute(
                    text("INSERT INTO merchants (merchant_no, merchant_name, status) VALUES (:no, :name, 1)"),
                    {"no": merchant_no, "name": req.merchant_name}
                )
                # 使用 SQLAlchemy 结果集的 lastrowid
                res_id = res.lastrowid
                
                # 3. 创建人员
                hashed_pwd = get_password_hash(req.password)
                conn.execute(
                    text("INSERT INTO personnel (merchant_id, username, password_hash, role, status) VALUES (:mid, :u, :p, 'admin', 1)"),
                    {"mid": res_id, "u": req.username, "p": hashed_pwd}
                )
        return {"status": "success", "message": "注册成功，请开始登录"}

    try:
        return await run_in_threadpool(do_register)
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        print(f"[Register Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(req: UserLogin):
    def do_login():
        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT p.merchant_id, p.password_hash, m.merchant_no FROM personnel p JOIN merchants m ON p.merchant_id = m.id WHERE p.username = :u"),
                {"u": req.username}
            ).fetchone()
            
            if not user or not verify_password(req.password, user[1]):
                raise HTTPException(status_code=400, detail="用户名或密码错误")
            
            token = create_access_token(data={"sub": req.username, "merchant_id": user[0], "merchant_no": user[2]})
            return {"access_token": token, "token_type": "bearer", "merchant_id": user[0], "merchant_no": user[2]}
    
    try:
        return await run_in_threadpool(do_login)
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    graph = create_assistant_graph()
    initial_state = {
        "messages": [HumanMessage(content=request.query)],
        "next_route": "",
        "merchant_id": user["merchant_id"],
        "merchant_no": user["merchant_no"]
    }
    
    try:
        # [DEBUG] 在请求开始时显著打印
        print(f"\n>>>> [API Request Start] 用户: {user['sub']} | 查询: {request.query}")
        
        final_state = initial_state
        # 使用 stream 模式遍历节点执行
        # 即使是异步 FastAPI 接口，我们也在线程池中运行同步的 graph 迭代
        def run_graph():
            nonlocal final_state
            # stream 会生成 (node_name, state_update) 的元组
            for output in graph.stream(initial_state, config={"recursion_limit": 10}):
                for node_name, state_update in output.items():
                    print(f"  [Node Execution] ---> 正在运行节点: {node_name}")
                    # 手动更新 state 以便最后获取
                    if state_update:
                        for k, v in state_update.items():
                            if k == "messages":
                                final_state["messages"] += v
                            else:
                                final_state[k] = v
            return final_state

        final_state = await run_in_threadpool(run_graph)
        
        print("<<<< [API Request End] 图执行完成\n")

        all_msgs = final_state.get("messages", [])
        
        if len(all_msgs) > 1: # 排除掉用户自己的提问
            last_msg = all_msgs[-1]
            raw = last_msg.content
            
            # 兼容 Gemini 新版 list[dict] 格式
            if isinstance(raw, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in raw
                )
            else:
                content = str(raw) if raw else ""
            
            content = content.strip()
            
            if not content or content == "[]":
                response_messages = ["该查询暂时没有找到匹配的回复，建议换个问法。"]
            else:
                response_messages = [content]
        else:
            response_messages = ["网络波动，请重试。"]

        return {
            "messages": response_messages,
            "final_route": final_state.get("next_route", "FINISH")
        }
    except Exception as e:
        print(f"[Chat Error] {e}")
        # 如果是 LLM 调用错误（例如 API 连接问题），通常表现为模型相关的异常
        if "Google" in str(e) or "API" in str(e) or "connection" in str(e).lower():
            return {
                "messages": ["网络波动，请重试。"],
                "final_route": "ERROR"
            }
        raise HTTPException(status_code=500, detail=f"智能体流转失败: {str(e)}")

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    接收用户上传的文件并导入 RAG 向量知识库
    """
    import os
    import shutil
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        # 保存到本地 uploads 目录
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 调用核心文档处理器切片并存储
        chunks_count = kb_manager.process_and_store_file(file_path)
        
        return {
            "status": "success", 
            "message": f"文件 '{file.filename}' 处理完成并录入知识库",
            "chunks_added": chunks_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")

@app.get("/pending_questions")
async def get_pending_questions():
    """获取所有待人工审核处理的失败对话"""
    return qa_manager.get_pending()

@app.post("/approve_question")
async def approve_question(req: QAApproveRequest):
    """人工审批并录入知识库，形成数据飞轮"""
    try:
        qa_manager.resolve_pending(req.id, req.answer)
        kb_manager.add_qa_pair(req.question, req.answer)
        return {"status": "success", "message": "飞轮数据已入库"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"录入知识库失败: {str(e)}")

@app.delete("/delete_question/{item_id}")
async def delete_question(item_id: int):
    """删除一条待审核记录（标记为 dismissed，不再展示）"""
    try:
        qa_manager.dismiss_pending(item_id)
        return {"status": "success", "message": "已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/health")
async def health_check():
    return {"status": "ok", "agents_registered": len(get_graph().nodes)}
