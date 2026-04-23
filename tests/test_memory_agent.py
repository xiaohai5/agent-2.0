"""
Memory Agent 单元测试
"""
import pytest
import time
from backend.app.agent.memory_agent import MemoryAgent
from backend.app.agent.memory_state import MessageDict


@pytest.fixture
def memory_agent():
    """创建 Memory Agent 实例"""
    return MemoryAgent()


@pytest.fixture
def sample_message():
    """创建示例消息"""
    return MessageDict(
        role="user",
        content="我想去北京旅游，预算大概 3000 元，喜欢历史文化类的景点",
        timestamp=time.time(),
        metadata=None
    )


class TestMemoryAgent:
    """Memory Agent 测试类"""

    def test_initialize_memory(self, memory_agent):
        """测试初始化记忆"""
        memory_state = memory_agent.initialize_memory()

        assert memory_state["current_user_input"] == ""
        assert len(memory_state["recent_full_memory"]) == 0
        assert len(memory_state["mid_compressed_memory"]) == 0
        assert memory_state["long_term_summary"] is None
        assert memory_state["total_message_count"] == 0

    @pytest.mark.asyncio
    async def test_compress_message(self, memory_agent, sample_message):
        """测试消息压缩"""
        compressed = await memory_agent.compress_message(sample_message)

        assert compressed.role == "user"
        assert len(compressed.compressed_content) > 0
        assert compressed.compressed_length < compressed.original_length
        assert compressed.compressed_length == len(compressed.compressed_content)

    @pytest.mark.asyncio
    async def test_update_memory_basic(self, memory_agent):
        """测试基础记忆更新"""
        memory_state = memory_agent.initialize_memory()

        # 第一轮更新
        memory_state = await memory_agent.update_memory(
            memory_state=memory_state,
            new_user_message="我想去北京旅游",
            new_assistant_message="好的，我可以帮您规划北京之旅",
            tool_calls=None
        )

        assert len(memory_state["recent_full_memory"]) == 2
        assert memory_state["total_message_count"] == 2
        assert memory_state["recent_full_memory"][0]["role"] == "user"
        assert memory_state["recent_full_memory"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_memory_layering(self, memory_agent):
        """测试记忆分层"""
        memory_state = memory_agent.initialize_memory()

        # 添加 6 轮对话（12 条消息）
        for i in range(6):
            memory_state = await memory_agent.update_memory(
                memory_state=memory_state,
                new_user_message=f"用户消息 {i+1}",
                new_assistant_message=f"助手回复 {i+1}",
                tool_calls=None
            )

        # 检查分层
        assert len(memory_state["recent_full_memory"]) == 5  # 最近 5 条
        assert len(memory_state["mid_compressed_memory"]) > 0  # 有压缩记忆
        assert memory_state["total_message_count"] == 12

    @pytest.mark.asyncio
    async def test_long_term_summary_generation(self, memory_agent):
        """测试长期摘要生成"""
        memory_state = memory_agent.initialize_memory()

        # 添加 12 轮对话（24 条消息）
        for i in range(12):
            memory_state = await memory_agent.update_memory(
                memory_state=memory_state,
                new_user_message=f"用户消息 {i+1}",
                new_assistant_message=f"助手回复 {i+1}",
                tool_calls=None
            )

        # 检查长期摘要
        assert memory_state["long_term_summary"] is not None
        assert len(memory_state["recent_full_memory"]) == 5
        assert len(memory_state["mid_compressed_memory"]) <= 5

    def test_get_memory_context(self, memory_agent):
        """测试获取记忆上下文"""
        memory_state = memory_agent.initialize_memory()

        # 添加一些数据
        memory_state["recent_full_memory"] = [
            MessageDict(
                role="user",
                content="测试消息",
                timestamp=time.time(),
                metadata=None
            )
        ]

        context = memory_agent.get_memory_context(memory_state)

        assert "recent_full_memory" in context
        assert "mid_compressed_memory" in context
        assert "long_term_summary" in context
        assert "latest_tool_results" in context
        assert len(context["recent_full_memory"]) == 1

    @pytest.mark.asyncio
    async def test_tool_calls_handling(self, memory_agent):
        """测试工具调用处理"""
        memory_state = memory_agent.initialize_memory()

        tool_calls = [
            {
                "tool_name": "search_poi",
                "action": "搜索景点",
                "key_params": {"city": "北京"},
                "result_summary": "找到 10 个景点",
                "success": True
            }
        ]

        memory_state = await memory_agent.update_memory(
            memory_state=memory_state,
            new_user_message="推荐景点",
            new_assistant_message="推荐故宫、长城",
            tool_calls=tool_calls
        )

        assert len(memory_state["latest_tool_results"]) == 1
        assert memory_state["latest_tool_results"][0].tool_name == "search_poi"

    @pytest.mark.asyncio
    async def test_memory_update_log(self, memory_agent):
        """测试记忆更新日志"""
        memory_state = memory_agent.initialize_memory()

        # 添加足够多的消息以触发压缩
        for i in range(6):
            memory_state = await memory_agent.update_memory(
                memory_state=memory_state,
                new_user_message=f"消息 {i+1}",
                new_assistant_message=f"回复 {i+1}",
                tool_calls=None
            )

        # 检查更新日志
        assert len(memory_state["memory_update_log"]) > 0
        assert memory_state["memory_update_log"][-1].action == "moved_to_compressed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
