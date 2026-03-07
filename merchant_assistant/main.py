import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from merchant_assistant.core.state import AgentState
from merchant_assistant.core.router import router_node
from merchant_assistant.core.registry import AGENT_REGISTRY

# 注意：需要把所有 agent import 进来以触发它们文件里的 @register_agent 装饰器
import merchant_assistant.agents.rag_agent
import merchant_assistant.agents.db_agent
import merchant_assistant.agents.summarize_agent

def create_assistant_graph():
    """
    构建多智能体工作流图
    """
    # 1. 初始化图结构
    workflow = StateGraph(AgentState)
    
    # 2. 添加核心的 Router 节点
    workflow.add_node("router", router_node)
    
    # 3. 动态从注册表中读取并添加所有具体能力的 Agent 节点
    for name, info in AGENT_REGISTRY.items():
        workflow.add_node(name, info["node_func"])
        
    # 假设 summarize_agent 是特别对待的终点节点 (或者它也在注册表中)
    # 如果它通过装饰器注册了，上面循环已经加了。这里为演示其特殊流转，假设它存在
    
    # 4. 设置入口为 router
    workflow.set_entry_point("router")
    
    # 5. 定义路由分支逻辑 (Conditional Edges)
    def route_condition(state: AgentState):
        """取出 router 节点刚写入 state 的 next_route 字段"""
        return state.get("next_route", "FINISH")
    
    # 从 registry 中取出所有 agent 名称
    registered_agents = list(AGENT_REGISTRY.keys())
    
    # 构建路由映射字典，建立 Router -> 目标节点的操作
    route_mapping = {agent: agent for agent in registered_agents}
    # 增加内置终结/后置流程
    route_mapping["FINISH"] = END
    if "summarize_agent" not in route_mapping:
         route_mapping["summarize_agent"] = "summarize_agent"

    # 添加 Router 的条件分发边
    workflow.add_conditional_edges("router", route_condition, route_mapping)
    
    # 6. 定义从 Worker Agent 到下游节点的边
    
    # summarize_agent：终点，直接结束
    workflow.add_edge("summarize_agent", END)
    
    # db_agent：无条件流入 summarize_agent（查询结果需要整合润色）
    workflow.add_edge("db_agent", "summarize_agent")
    
    # rag_agent：条件边
    #   - next_route == "FINISH" → 直接结束（知识库无答案，已推入人工审核）
    #   - next_route == "summarize_agent" → 流入总结节点
    def rag_route_condition(state: AgentState):
        return state.get("next_route", "summarize_agent")
    
    workflow.add_conditional_edges(
        "rag_agent",
        rag_route_condition,
        {
            "FINISH": END,
            "summarize_agent": "summarize_agent",
        }
    )

    # 7. 编译生成可运行对象
    app = workflow.compile()
    return app

if __name__ == "__main__":
    # 测试图构建
    app = create_assistant_graph()
    print("Graph compiled successfully!")
    # 可以将其打印为 mermaid 图 (需安装必要组件)
    # print(app.get_graph().draw_mermaid())
