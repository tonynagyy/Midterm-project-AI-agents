from typing import TypedDict, Annotated, List, Union, Optional
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    question: str
    sql_query: Optional[str]
    sql_result: Optional[Union[List[dict], str]]
    error: Optional[str]
    revision_count: int