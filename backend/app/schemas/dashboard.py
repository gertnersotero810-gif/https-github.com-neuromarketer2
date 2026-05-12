from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Widget(BaseModel):
    i: str
    x: int
    y: int
    w: int
    h: int
    chart: Literal["line", "bar", "pie", "area", "number"]
    dataKey: str
    title: str
    filters: Optional[dict] = None
    data: Optional[List[dict]] = None

class DashboardResponse(BaseModel):
    widgets: List[Widget]

class DashboardLayoutUpdate(BaseModel):
    widgets: List[Widget]
