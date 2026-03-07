from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from merchant_assistant.core.state import AgentState
from merchant_assistant.core.registry import register_agent
from merchant_assistant.core.document_processor import kb_manager
from merchant_assistant.core.prompt_loader import load_prompt
from merchant_assistant.core.qa_manager import qa_manager
from merchant_assistant.core.config import settings

# 置信度阈值：低于此值则进入人工审核（0=最差，1=最好）
# Chroma 距离 0.5 → conf = 75%；距离 1.0 → conf = 50%；设 0.6 排除低质量匹配
CONFIDENCE_THRESHOLD = 0.6

@register_agent(
    name="rag_agent",
    description=load_prompt("rag_desc.md")
)
def rag_agent_node(state: AgentState):
    """
    RAG Agent 节点：
    1. 从向量知识库检索相关片段
    2. 若置信度足够，调用 LLM 基于检索内容回答问题（不传原始 chunk 下去）
    3. 若置信度不足，加入人工审核队列并直接 FINISH
    """
    messages = state["messages"]
    if not messages:
        return {"next_route": "summarize_agent"}

    last_user_message = messages[-1].content
    print(f"\n[RAG Agent] 检索问题: {last_user_message}")

    # === 1. 向量检索 ===
    docs_with_conf = kb_manager.retrieve_with_confidence(last_user_message, top_k=3)
    best_conf = docs_with_conf[0][1] if docs_with_conf else 0.0
    print(f"[RAG Agent] 最高置信度: {best_conf:.2%}")

    # === 2. 置信度不足 → 加入人工审核队列，传兜底消息给 summarize_agent ===
    if best_conf < CONFIDENCE_THRESHOLD or not docs_with_conf:
        print(f"[RAG Agent] 置信度不足 ({best_conf:.2%} < {CONFIDENCE_THRESHOLD:.0%})，推入人工审核队列")

        # 用 LLM 提炼问题，失败则用原文
        llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            temperature=0,
            safety_settings=settings.SAFETY_SETTINGS
        )
        try:
            refine_prompt = (
                f"请将下面这个口语化的问题，提炼为一个简洁、标准的知识库问答问题。"
                f"不需要解释，只输出提炼后的问题本身：\n\n{last_user_message}"
            )
            raw_refined = llm.invoke(refine_prompt).content
            if isinstance(raw_refined, list):
                refined_query = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_refined).strip()
            else:
                refined_query = str(raw_refined).strip()
        except Exception as e:
            print(f"[RAG Agent] 提炼问题异常: {e}")
            refined_query = last_user_message

        qa_manager.add_pending(last_user_message, refined_query)
        print(f"[RAG Agent] 已录入待审核问题: {refined_query}")

        # 传兜底消息给 summarize_agent，让它输出自然语言
        fallback_msg = (
            f"[知识库无结果]: 用户询问「{last_user_message}」，"
            f"知识库中未找到置信度足够的内容（最高 {best_conf:.0%}）。"
            f"问题已自动转入人工审核队列，审核通过后答案将同步入库。"
            f"请以友好语气告知用户暂时无法作答，并说明问题已在处理中。"
        )
        return {
            "messages": [AIMessage(content=fallback_msg)],
            "next_route": "summarize_agent"
        }

    # === 3. 置信度足够 → 用 LLM 根据检索内容生成自然语言回答 ===
    context_parts = []
    for doc, conf in docs_with_conf:
        context_parts.append(doc.page_content)
    retrieved_context = "\n\n".join(context_parts)

    print(f"[RAG Agent] 检索成功，调用 LLM 生成回答...")

    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_PRO,
        temperature=0.3,
        safety_settings=settings.SAFETY_SETTINGS
    )

    qa_prompt = (
        f"你是一个商户服务助手。请根据下方知识库内容，用简洁、友好的中文回答用户的问题。\n"
        f"如果知识库内容不足以完整回答，请如实说明，不要捏造信息。\n\n"
        f"【知识库内容】\n{retrieved_context}\n\n"
        f"【用户问题】\n{last_user_message}\n\n"
        f"请直接给出答案，不要重复用户的问题。"
    )

    try:
        response = llm.invoke(qa_prompt)
        raw = response.content
        if isinstance(raw, list):
            answer = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw).strip()
        else:
            answer = str(raw).strip()

        if not answer:
            answer = "根据知识库内容，暂时无法提供明确答案，请联系人工客服。"
    except Exception as e:
        print(f"[RAG Agent] LLM 调用异常: {e}")
        answer = "网络波动，请重试。"

    print(f"[RAG Agent] 回答生成完毕: {answer[:80]}...")

    # RAG 直接给出答案，传给 summarize_agent 做最终整合
    return {
        "messages": [AIMessage(content=f"[知识库回答]:\n{answer}")],
        "next_route": "summarize_agent"
    }
