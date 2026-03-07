from typing import Callable, Dict, Any

# 全局的 Agent 注册表
# 结构: { "agent_name": { "description": "...", "node_func": node_function } }
AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {}

def register_agent(name: str, description: str):
    """
    装饰器：用于向注册表中动态注册 Agent
    """
    def decorator(func: Callable):
        AGENT_REGISTRY[name] = {
            "description": description,
            "node_func": func
        }
        return func
    return decorator

def get_agent_descriptions() -> str:
    """
    获取所有已注册 Agent 的描述，用于构建 Router 的 Prompt
    """
    descriptions = []
    for name, info in AGENT_REGISTRY.items():
        descriptions.append(f"- {name}: {info['description']}")
    return "\n".join(descriptions)
