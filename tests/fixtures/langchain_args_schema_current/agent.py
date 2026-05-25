from langchain.tools import StructuredTool, Tool
from pydantic import BaseModel, Field


class OrderLookupInput(BaseModel):
    order_id: str = Field(..., description="Order identifier to look up.")
    include_history: bool = Field(False, description="Whether to include historical status changes.")
    limit: int = 5


def lookup_order(order_id: str, include_history: bool = False, limit: int = 5) -> str:
    return order_id


lookup_order_tool = StructuredTool.from_function(
    lookup_order,
    name="lookup_order",
    description="Lookup an order by id.",
    args_schema=OrderLookupInput,
)

unresolved_tool = Tool(
    name="unresolved_search",
    func=lookup_order,
    description="Search with an unresolved schema.",
    args_schema=MissingInput,
)
