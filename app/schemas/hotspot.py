"""
热点数据 Schema
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HotspotResponse(BaseModel):
    """热点响应模型"""
    platform: str
    title: str
    heat: int
    url: str
    timestamp: Optional[str] = None
    rank: Optional[int] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True
