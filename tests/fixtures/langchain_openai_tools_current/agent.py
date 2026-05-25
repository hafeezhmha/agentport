from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

SYSTEM_TEMPLATE = "You are an OpenAI tools agent. Use tools only when they improve answer quality."
USER_TEMPLATE = "{input}"


@tool
def search_orders(query: str) -> str:
    """Search order records."""
    return query


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TEMPLATE),
        ("human", USER_TEMPLATE),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_openai_tools_agent(llm, [search_orders], prompt)
executor = AgentExecutor(agent=agent, tools=[search_orders])
