from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
# 使用 Gemini 作为推断模型
from langchain_google_genai import ChatGoogleGenerativeAI
from merchant_assistant.core.config import settings
from pydantic import BaseModel, Field
from typing import Literal, Type

from merchant_assistant.core.state import AgentState
from merchant_assistant.core.registry import get_agent_descriptions, AGENT_REGISTRY
from merchant_assistant.core.prompt_loader import load_prompt

# 预期的路由输出结构
class RouteOutput(BaseModel):
    next_route: str = Field(
        description="下一步要调用的 Agent 名称，如果无法识别或无需调用则返回 FINISH"
    )

def detect_intent_heuristics(query: str) -> str:
    """简单启发式意图识别，防止 LLM 出错时流程中断"""
    query = query.strip()
    if any(k in query for k in ["查询", "多少", "比", "订单", "金额", "统计"]):
        return "db_agent"
    if any(k in query for k in ["什么", "怎么", "如何", "指南", "手册", "流程"]):
        return "rag_agent"
    return "summarize_agent"

def router_node(state: AgentState):
    """
    路由节点：读取当前状态(messages)和可用的 Agents 描述，
    调用 LLM 决定把任务派发给哪个具体的 Agent。
    """
    messages = state.get("messages", [])
    merchant_id = state.get("merchant_id")
    merchant_no = state.get("merchant_no")
    
    print(f"[Router] 当前商户 ID: {merchant_id}, 商户号: {merchant_no}")
    print(f"[Router] 请求模型: {settings.LLM_MODEL}")
    
    if not messages:
        return {"next_route": "FINISH"}
    
    last_query = messages[-1].content
    agent_descriptions = get_agent_descriptions()
    valid_routes = list(AGENT_REGISTRY.keys()) + ["FINISH", "summarize_agent"]
    
    system_prompt_template = load_prompt("router_system.md")
    system_prompt = system_prompt_template.format(
        agent_descriptions=agent_descriptions,
        valid_routes=", ".join(valid_routes)
    )
    
    # 路由使用 Flash 模型，响应极快
    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_FAST, 
        temperature=settings.TEMPERATURE_ROUTER,
        safety_settings=settings.SAFETY_SETTINGS
    )
    structured_llm = llm.with_structured_output(RouteOutput)
    
    prompt_messages = [SystemMessage(content=system_prompt)] + list(messages)
    
    try:
        response = structured_llm.invoke(prompt_messages)
        next_route = response.next_route
        
        print(f"  [Router Decision] 模型原始输出: {next_route}")
        
        # 如果模型返回了 FINISH 但看起来像个问题，进行暴力纠偏
        if next_route == "FINISH" and len(last_query) > 3:
            heuristic_route = detect_intent_heuristics(last_query)
            print(f"  [Router Decision] 检测到可能的意图误判，触发启发式纠偏: {heuristic_route}")
            next_route = heuristic_route
        
        if next_route not in valid_routes:
            print(f"  [Router Decision] 路径 {next_route} 无效，默认流向 summarize_agent")
            next_route = "summarize_agent"
                
    except Exception as e:
        print(f"  [Router Decision] LLM 异常: {e}")
        # LLM 调用失败（如模型名称无效或 API Key 没配），走启发式兜底逻辑
        next_route = detect_intent_heuristics(last_query)
        print(f"  [Router Decision] 触发兜底路径: {next_route}")
        
    print(f"  [Router Decision] >>> 最终流向节点: {next_route}")
    return {"next_route": next_route}
