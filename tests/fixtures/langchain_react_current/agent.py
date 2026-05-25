from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.tools import tool
from langchain_community.vectorstores import FAISS

SYSTEM_TEMPLATE = "You are a current LangChain ReAct agent. Use retrieved context carefully."
USER_TEMPLATE = "Question: {question}"


@tool
def search_docs(query: str) -> str:
    """Search internal docs."""
    return query


prompt = PromptTemplate.from_template(SYSTEM_TEMPLATE)
chat_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TEMPLATE),
        ("human", USER_TEMPLATE),
    ]
)

retriever = FAISS.as_retriever()
agent = create_react_agent(llm, [search_docs], prompt)
executor = AgentExecutor(agent=agent, tools=[search_docs])
