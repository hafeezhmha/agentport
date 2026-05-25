from langgraph.graph import StateGraph
from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = "You are a support triage agent. Classify urgency, summarize the issue, and ask only necessary follow-up questions."
MODEL_NAME = "gpt-4o-mini"


def triage_node(state):
    return {"summary": state["message"]}


graph = StateGraph(dict)
graph.add_node("triage", triage_node)
