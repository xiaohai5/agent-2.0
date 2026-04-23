"""
Dual Agent Workflow 集成测试
"""
import pytest
from pathlib import Path
from backend.app.agent.dual_agent_workflow import DualAgentWorkflow
from backend.app.agent.memory_agent import MemoryAgent


@pytest.fixture
def workflow():
    """创建工作流实例"""
    skill_path = Path(__file__).resolve().parents[1] / "skills" / "travel-life-service-auto-router" / "SKILL.md"
    return DualAgentWorkflow(skill_path=skill_path)


@pytest.fixture
def memory_agent():
    """创建 Memory Agent 实例"""
    return MemoryAgent()


class TestDualAgentWorkflow:
    """Dual Agent Workflow 测试类"""

    @pytest.mark.asyncio
    async def test_workflow_basic_run(self, workflow):
        """测试基础工作流运行"""
        answer, memory_state = await workflow.run(
            user_input="我想去北京旅游",
            user_id=123,
            top_k=5,
            memory_state=None
        )

        assert isinstance(answer, str)
        assert len(answer) > 0
        assert memory_state is not None
        assert len(memory_state["recent_full_memory"]) == 2  # 用户 + 助手

    @pytest.mark.asyncio
    async def test_workflow_multi_turn(self, workflow):
        """测试多轮对话"""
        # 第一轮
        answer1, memory1 = await workflow.run(
            user_input="我想去北京旅游",
            user_id=123,
            top_k=5,
            memory_state=None
        )

        # 第二轮
        answer2, memory2 = await workflow.run(
            user_input="推荐一些景点",
            user_id=123,
            top_k=5,
            memory_state=memory1
        )

        assert len(memory2["recent_full_memory"]) == 4  # 2 轮 * 2 条
        assert memory2["total_message_count"] == 4

    @pytest.mark.asyncio
    async def test_workflow_memory_persistence(self, workflow):
        """测试记忆持久化"""
        memory_state = None

        # 进行 3 轮对话
        questions = ["去北京", "推荐景点", "推荐酒店"]

        for question in questions:
            answer, memory_state = await workflow.run(
                user_input=question,
                user_id=123,
                top_k=5,
                memory_state=memory_state
            )

        # 检查记忆累积
        assert memory_state["total_message_count"] == 6  # 3 轮 * 2 条

    @pytest.mark.asyncio
    async def test_workflow_stream(self, workflow):
        """测试流式输出"""
        events = []

        async for event in workflow.run_stream(
            user_input="我想去北京旅游",
            user_id=123,
            top_k=5,
            memory_state=None
        ):
            events.append(event)

        # 检查事件
        assert len(events) > 0
        assert any(e.get("type") == "chunk" for e in events)
        assert any(e.get("type") == "done" for e in events)

    @pytest.mark.asyncio
    async def test_memory_context_retrieval(self, workflow, memory_agent):
        """测试记忆上下文检索"""
        # 初始化记忆
        memory_state = memory_agent.initialize_memory()

        # 添加一些历史
        memory_state = await memory_agent.update_memory(
            memory_state=memory_state,
            new_user_message="我想去北京",
            new_assistant_message="好的",
            tool_calls=None
        )

        # 运行工作流
        answer, updated_memory = await workflow.run(
            user_input="推荐景点",
            user_id=123,
            top_k=5,
            memory_state=memory_state
        )

        # 检查记忆是否被使用
        assert len(updated_memory["recent_full_memory"]) == 4

    @pytest.mark.asyncio
    async def test_priority_rules(self, workflow, memory_agent):
        """测试优先级规则"""
        # 创建有历史的记忆
        memory_state = memory_agent.initialize_memory()
        memory_state = await memory_agent.update_memory(
            memory_state=memory_state,
            new_user_message="我想去上海",
            new_assistant_message="好的，上海很不错",
            tool_calls=None
        )

        # 当前输入与历史冲突
        answer, updated_memory = await workflow.run(
            user_input="我想去北京，不是上海",
            user_id=123,
            top_k=5,
            memory_state=memory_state
        )

        # 回答应该以当前输入为准（北京）
        assert "北京" in answer or "beijing" in answer.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
