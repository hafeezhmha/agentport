from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

SYSTEM_PROMPT = "You are an email triage agent. Classify urgency and route to the right specialist."
MODEL_NAME = "gpt-4o-mini"


class EmailState(TypedDict):
    message: str
    classification: str


def classify(state: EmailState):
    return {"classification": "urgent"}


def route(state: EmailState):
    if state["classification"] == "urgent":
        return "escalate"
    return "draft"


def escalate(state: EmailState) -> Command:
    return Command(update={"classification": "escalated"}, goto="draft")


def fanout(state: EmailState):
    return [Send("draft", {"message": state["message"]})]


builder = StateGraph(EmailState)
builder.add_node("classify", classify)
builder.add_node("escalate", escalate)
builder.add_node("draft", lambda state: {"message": state["message"]})
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route, {"urgent": "escalate", "normal": "draft"})
builder.add_edge("draft", END)
graph = builder.compile()
