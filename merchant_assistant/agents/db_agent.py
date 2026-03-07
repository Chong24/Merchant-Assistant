from langchain_core.messages import AIMessage
from merchant_assistant.core.state import AgentState
from merchant_assistant.core.registry import register_agent
from merchant_assistant.core.db_processor import db_manager
from merchant_assistant.core.prompt_loader import load_prompt

@register_agent(
    name="db_agent",
    description=load_prompt("db_desc.md")
)
def db_agent_node(state: AgentState):
    """
    DB Agent 节点：
    这里应当接入 SQLDatabase / SQL Toolkit，Text-to-SQL 的能力。
    """
    messages = state["messages"]
    merchant_id = state.get("merchant_id")
    merchant_no = state.get("merchant_no")
    
    if not messages:
        return {"next_route": "summarize_agent"}
        
    last_user_message = messages[-1].content
    
    print(f"[DB Agent] 商户 {merchant_no} 正在查询: {last_user_message} ...")
    
    # 传递商户上下文，确保数据隔离
    sql_result = db_manager.query(last_user_message, merchant_id=merchant_id)
    
    print(f"[DB Agent] 查询完成。")
    
    # 将数据库查询结果追加到全局历史
    response_message = AIMessage(content=f"[数据库查询结果]:\n{sql_result}")
    
    return {
        "messages": [response_message],
        "next_route": "summarize_agent"
    }
