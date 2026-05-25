from crewai import Agent, Crew, Task

researcher = Agent(
    role="Legacy Researcher",
    goal="Research old CrewAI examples.",
    backstory="You work in a direct-code CrewAI repo with no YAML config.",
)

task = Task(
    description="Find migration risks in legacy CrewAI syntax.",
    expected_output="A short risk list.",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task])
