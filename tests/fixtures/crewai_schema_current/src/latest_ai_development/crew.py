from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from pydantic import BaseModel


class ReportSchema(BaseModel):
    title: str
    body: str


@CrewBase
class LatestAiDevelopmentCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            role="Senior AI Researcher",
            goal="Find current, source-backed evidence.",
            backstory="You are skeptical, precise, and cite source uncertainty.",
            tools=[SerperDevTool()],
            llm="gpt-4o-mini",
            memory=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            description="Research current framework schemas.",
            expected_output="A sourced field map.",
            guardrail="Must separate identity from runtime.",
            output_pydantic=ReportSchema,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.researcher()],
            tasks=[self.research_task()],
            process=Process.hierarchical,
            manager_llm="gpt-4o",
        )
