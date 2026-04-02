import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


def strip_think_tags(text):
    return re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL).strip()


def main():
    llm = ChatOpenAI(
        model="qwen35-4b",
        base_url="http://localhost:1522/v1",
        api_key="123456",
    )

    messages = [
        SystemMessage(content="你你是中文智能客服总结助手，输出可爱搞怪但专业、信息完整、不遗漏关键事实、带有表情的最终客服回复"),
        HumanMessage(content="请简单介绍一下北京的旅游特点。"),
    ]

    try:
        response = llm.invoke(messages)
        content = strip_think_tags(response.content)
        print("模型回复：")
        print(content)
    except Exception as e:
        print("调用模型失败：", e)


if __name__ == "__main__":
    main()
