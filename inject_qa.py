import os
from dotenv import load_dotenv
load_dotenv()

from merchant_assistant.core.document_processor import kb_manager

question = "翼办通平台上橙分期产品的签约流程是什么？"
answer = (
    "1、微信搜索翼办通小程序；"
    "2、点击我是商户，用商户账号登录；"
    "3、点击橙分期卡片，通过法人身份验证后即可完成签约"
)

kb_manager.add_qa_pair(question, answer)
print("已写入知识库：")
print("Q:", question)
print("A:", answer)
