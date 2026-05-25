from crewai import Agent, Crew, Task

researcher = Agent(
    role="Market Researcher",
    goal="Find evidence without overstating certainty.",
    backstory="You prefer primary sources and clearly label assumptions.",
    llm="gpt-4o-mini",
)

task = Task(
    description="Summarize source evidence.",
    expected_output="A bullet list of claims with source notes.",
)

crew = Crew(agents=[researcher], tasks=[task])
