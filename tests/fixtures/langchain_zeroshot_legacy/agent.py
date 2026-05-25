from langchain.agents import AgentExecutor, Tool, ZeroShotAgent
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

PREFIX = "You are a legacy ZeroShotAgent. Select tools carefully."
SUFFIX = "Question: {input}\n{agent_scratchpad}"

search = Tool(name="search", func=lambda q: q, description="Search for a query")
prompt = ZeroShotAgent.create_prompt([search], prefix=PREFIX, suffix=SUFFIX)
llm_chain = LLMChain(llm=llm, prompt=prompt)
agent = ZeroShotAgent.from_llm_and_tools(llm=llm, tools=[search], prefix=PREFIX, suffix=SUFFIX)
executor = AgentExecutor(agent=agent, tools=[search])
