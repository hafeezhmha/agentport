from langchain.agents import AgentExecutor, Tool, initialize_agent
from langchain.llms import OpenAI

SYSTEM_PROMPT = "You are a legacy LangChain ReAct agent. Use tools carefully and explain final answers."

search = Tool(name="search", func=lambda q: q, description="Search for a query")
llm = OpenAI(model_name="gpt-3.5-turbo-instruct")
agent = initialize_agent([search], llm, agent="zero-shot-react-description")
executor = AgentExecutor(agent=agent, tools=[search])
