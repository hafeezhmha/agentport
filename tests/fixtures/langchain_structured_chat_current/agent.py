from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

SYSTEM_TEMPLATE = "You are a structured chat support agent. Validate account context before answering."
USER_TEMPLATE = "{input}"


@tool
def lookup_account(account_id: str) -> str:
    """Look up a customer account."""
    return account_id


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TEMPLATE),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", USER_TEMPLATE),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_structured_chat_agent(llm=llm, tools=[lookup_account], prompt=prompt)
executor = AgentExecutor(agent=agent, tools=[lookup_account], verbose=True)
