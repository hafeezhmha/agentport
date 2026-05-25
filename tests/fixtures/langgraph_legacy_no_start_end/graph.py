from langgraph.graph import StateGraph

PROMPT = "You are a legacy graph node that summarizes requests."


def summarize(state):
    return {"summary": state["message"]}


graph = StateGraph(dict)
graph.add_node("summarize", summarize)
graph.set_entry_point("summarize")
graph.set_finish_point("summarize")
compiled = graph.compile()
