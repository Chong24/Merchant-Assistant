import operator
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    统一的 AgentState，在图中的所有节点间流转
    """
    # 消息记录。使用 operator.add 将新消息追加到现有列表中，而不是覆盖
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # 路由指令，用于 Router 决定下一个调用的节点名称，或者直接结束
    next_route: str

    # 商户身份（回归修复：之前缺失导致 AgentState 无法正确传递这些字段）
    merchant_id: int
    merchant_no: str
