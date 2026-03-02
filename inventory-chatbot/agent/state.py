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
    intent: Optional[str] # 'sql' or 'chat'
    latency_ms: Optional[int]
    token_usage: Optional[dict] # {prompt_tokens, completion_tokens, total_tokens}
    first_failing_query: Optional[str]
    first_error: Optional[str]