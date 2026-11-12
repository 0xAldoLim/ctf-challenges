from agno.os import AgentOS

from app.agent import build_agent

agent = build_agent("agentos")
agent_os = AgentOS(agents=[agent])
app = agent_os.get_app()
