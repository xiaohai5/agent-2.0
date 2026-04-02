"""RAG response service."""

from langchain_classic.chains.llm import LLMChain
from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

try:
    from . import config_data as config
except ImportError:
    import config_data as config

try:
    from .creat_retriver import creat_retriver
except ImportError:
    from creat_retriver import creat_retriver


class rag_service(object):
    def __init__(self, splitter_params: dict | None = None, collection_name: str | None = None):
        self.retriever = creat_retriver(splitter_params, collection_name=collection_name)
        self.llm = ChatOpenAI(model=config.llm_model)
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=config.max_token_limit,
            memory_key="chat_history",
            return_messages=True,
            input_key="query",
        )

        self.chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", "请根据检索结果回答用户问题。"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "检索结果: {result}\n问题: {query}"),
            ]
        )

    def _format_result(self, result) -> str:
        if not result:
            return "未检索到相关内容。"

        formatted_chunks: list[str] = []
        for idx, doc in enumerate(result, start=1):
            content = getattr(doc, "page_content", "") or ""
            metadata = getattr(doc, "metadata", {}) or {}
            source = metadata.get("filename") or metadata.get("source") or "unknown"
            recall_type = metadata.get("_recall_type", "unknown")
            recall_query = metadata.get("_recall_query", "")
            rerank_score = metadata.get("_rerank_score", "")
            normalized_query = metadata.get("_normalized_query", "")
            final_rank = metadata.get("_final_rank", "")
            final_ranker = metadata.get("_final_ranker", "")
            formatted_chunks.append(
                f"[{idx}] source={source} recall_type={recall_type} "
                f"recall_query={recall_query} rerank_score={rerank_score} "
                f"normalized_query={normalized_query} final_rank={final_rank} "
                f"final_ranker={final_ranker}\n{content}"
            )
        return "\n\n".join(formatted_chunks)

    def _normalize_history(self, history: list[dict[str, str]] | None) -> list[object]:
        normalized: list[object] = []
        for item in history or []:
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if role == "assistant":
                normalized.append(AIMessage(content=content))
            else:
                normalized.append(HumanMessage(content=content))
        return normalized

    def get_response(self, query, history: list[dict[str, str]] | None = None, history_summary: str = ""):
        result = self.retriever.invoke(query)
        normalized_history = self._normalize_history(history)
        chain = LLMChain(
            llm=self.llm,
            prompt=self.chat_template,
            memory=None if normalized_history else self.memory,
        )
        response = chain.invoke(
            {
                "query": query,
                "result": self._format_result(result),
                "chat_history": normalized_history[-10:],
                "history_summary": str(history_summary or "").strip() or "无",
            }
        )
        return response["text"]
