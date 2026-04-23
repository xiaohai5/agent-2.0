"""
用户记忆模型 - 存储 Memory Agent 的记忆状态
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, Text

from backend.app.core.database import Base


class UserMemory(Base):
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True, comment="用户ID")
    memory_state = Column(JSON, nullable=False, comment="记忆状态（JSON格式）")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
