from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from merchant_assistant.core.state import AgentState
from merchant_assistant.core.registry import register_agent
from merchant_assistant.core.prompt_loader import load_prompt
from merchant_assistant.core.config import settings

@register_agent(
    name="summarize_agent",
    description=load_prompt("summarize_desc.md")
)
def summarize_agent_node(state: AgentState):
    """
    Summarize & Advice Agent 节点：
    作为工作流的最后一个环节，收集前面所有节点的消息上下文，
    结合大模型，输出针对商户的综合性建议。
    """
    messages = state["messages"]
    
    # [DEBUG] 打印输入上下文
    print("\n--- [Summarize Agent] 开始生成总结 & 建议 ---")
    print(f"当前上下文消息数量: {len(messages)}")
    for i, msg in enumerate(messages):
        content_preview = str(msg.content)[:100] + "..." if len(str(msg.content)) > 100 else str(msg.content)
        print(f"  [消息 {i}] ({type(msg).__name__}): {content_preview}")
    
    system_prompt = load_prompt("summarize_system.md")
    
    # 总结建议使用 Pro 模型，确保理解深度
    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_PRO, 
        temperature=settings.TEMPERATURE_SUMMARY,
        safety_settings=settings.SAFETY_SETTINGS
    )
    
    # 构造请求，包含 SystemPrompt 和 历史对话
    # 明确告知模型这是总结阶段，不要发散
    full_messages = [SystemMessage(content=system_prompt)] + list(messages)
    
    import time
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = llm.invoke(full_messages)
            raw = response.content
            
            # Gemini 新版 SDK 有时返回 list[dict] 格式，需要提取纯文本
            if isinstance(raw, list):
                final_content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in raw
                )
            else:
                final_content = str(raw) if raw else ""
            
            # 去除多余的 Markdown 标记，让输出更干净
            final_content = final_content.replace("\\n", "\n").strip()
            
            if not final_content:
                if messages:
                    final_content = "已收到您的信息。目前我没有找到相关内容，您可以尝试换种说法提问。"
                else:
                    final_content = "抱歉，由于会话上下文丢失，我无法生成总结建议。"
            break
        except Exception as e:
            error_msg = str(e)
            print(f"[Summarize Agent] 第 {attempt+1} 次尝试失败: {error_msg}")
            
            if "UNEXPECTED_EOF_WHILE_READING" in error_msg:
                if attempt < max_retries - 1:
                    time.sleep(1) # SSL 异常重试
                    continue
            
            if "API_KEY_INVALID" in error_msg or "valid API key" in error_msg:
                final_content = "网络波动，请重试。（API Key 配置检测异常）"
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                final_content = f"网络波动，请重试。（模型服务暂时不可用）"
            else:
                final_content = "网络波动，请重试。如多次出现，请检查您的网络连接。"
            break
    
    final_message = AIMessage(content=f"【总结与建议】:\n{final_content}")
    
    # [DEBUG] 打印输出记录
    print(f"[Summarize Agent] 最终生成内容预览: {final_content[:100]}...")
    print("--- [Summarize Agent] 处理结束 ---\n")
    
    return {
        "messages": [final_message],
        "next_route": "FINISH"
    }
