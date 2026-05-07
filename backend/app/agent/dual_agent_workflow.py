"""
双 Agent 工作流编排
使用 LangGraph 编排 Memory Agent 和 Dialog Agent 的协作流程
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from .dialog_agent import DialogAgent
from .memory_agent import MemoryAgent
from .memory_state import CombinedState, DialogState, MemoryState


class DualAgentWorkflow:
    """双 Agent 工作流 - 编排 Memory Agent 和 Dialog Agent"""

    def __init__(self, skill_path: str | Path) -> None:
        self.memory_agent = MemoryAgent()
        self.dialog_agent = DialogAgent(skill_path)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建 LangGraph 状态图"""
        workflow = StateGraph(CombinedState)

        # 添加节点
        workflow.add_node("retrieve_memory", self._retrieve_memory_node)
        workflow.add_node("prepare_tool_agents", self._prepare_tool_agents_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("update_memory", self._update_memory_node)

        # 定义边
        workflow.set_entry_point("retrieve_memory")
        workflow.add_edge("retrieve_memory", "prepare_tool_agents")
        workflow.add_edge("prepare_tool_agents", "generate_response")
        workflow.add_edge("generate_response", "update_memory")
        workflow.add_edge("update_memory", END)

        return workflow.compile()

    async def _retrieve_memory_node(self, state: CombinedState) -> dict[str, Any]:
        """节点 1: 从 Memory Agent 获取记忆上下文"""
        memory_state = state["memory_state"]

        # 更新当前用户输入
        memory_state["current_user_input"] = state["user_input"]

        # 获取记忆上下文
        memory_context = self.memory_agent.get_memory_context(memory_state)

        # 更新 dialog_state
        dialog_state = DialogState(
            current_input=state["user_input"],
            memory_context=memory_context,
            generated_response="",
            current_tool_calls=[],
        )

        return {
            "memory_state": memory_state,
            "dialog_state": dialog_state,
        }

    async def _prepare_tool_agents_node(self, state: CombinedState) -> dict[str, Any]:
        """Bind Dialog Agent to the 12306 and Amap tool agents before response generation."""
        await self.dialog_agent.prepare_tool_agents(user_id=state["user_id"], top_k=state["top_k"])
        return {
            "tool_agents_ready": True,
        }

    async def _generate_response_node(self, state: CombinedState) -> dict[str, Any]:
        """节点 2: Dialog Agent 生成回复"""
        dialog_state = state["dialog_state"]

        # 生成回复 - 现在返回 (text, poi_data)
        response, poi_data = await self.dialog_agent.generate_response(
            current_input=dialog_state["current_input"],
            memory_context=dialog_state["memory_context"],
            user_id=state["user_id"],
            top_k=state["top_k"],
        )

        dialog_state["generated_response"] = response

        return {
            "dialog_state": dialog_state,
            "final_answer": response,
            "pois": poi_data,
        }

    async def _update_memory_node(self, state: CombinedState) -> dict[str, Any]:
        """节点 3: Memory Agent 更新记忆"""
        memory_state = state["memory_state"]
        dialog_state = state["dialog_state"]

        # 更新记忆
        updated_memory = await self.memory_agent.update_memory(
            memory_state=memory_state,
            new_user_message=dialog_state["current_input"],
            new_assistant_message=dialog_state["generated_response"],
            tool_calls=dialog_state["current_tool_calls"],
        )

        return {
            "memory_state": updated_memory,
            "status": "completed",
        }

    async def run(
        self,
        user_input: str,
        user_id: int,
        top_k: int,
        memory_state: MemoryState | None = None,
    ) -> tuple[str, MemoryState]:
        """运行工作流"""
        # 初始化状态
        if memory_state is None:
            memory_state = self.memory_agent.initialize_memory()

        initial_state = CombinedState(
            user_input=user_input,
            user_id=user_id,
            top_k=top_k,
            memory_state=memory_state,
            dialog_state=DialogState(
                current_input="",
                memory_context={},
                generated_response="",
                current_tool_calls=[],
            ),
            final_answer="",
            pois=[],
            tool_agents_ready=False,
            status="processing",
        )

        # 执行工作流
        result = await self.graph.ainvoke(initial_state)

        return result["final_answer"], result["memory_state"], result.get("pois", [])

    async def run_stream(
        self,
        user_input: str,
        user_id: int,
        top_k: int,
        memory_state: MemoryState | None = None,
    ):
        """流式运行工作流"""
        # 初始化状态
        if memory_state is None:
            memory_state = self.memory_agent.initialize_memory()

        initial_state = CombinedState(
            user_input=user_input,
            user_id=user_id,
            top_k=top_k,
            memory_state=memory_state,
            dialog_state=DialogState(
                current_input="",
                memory_context={},
                generated_response="",
                current_tool_calls=[],
            ),
            final_answer="",
            pois=[],
            tool_agents_ready=False,
            status="processing",
        )

        # 执行工作流（流式）
        final_answer = ""
        final_pois = []
        final_memory = None

        async for event in self.graph.astream(initial_state):
            # 检查是否到达 generate_response 节点
            if "generate_response" in event:
                node_output = event["generate_response"]
                if "final_answer" in node_output:
                    final_answer = node_output["final_answer"]
                if "pois" in node_output:
                    final_pois = node_output["pois"]

            # 检查是否完成
            if "update_memory" in event:
                node_output = event["update_memory"]
                final_memory = node_output["memory_state"]
                yield {
                    "type": "done",
                    "answer": final_answer,
                    "pois": final_pois,
                    "memory_state": final_memory,
                    "status": node_output["status"],
                }
