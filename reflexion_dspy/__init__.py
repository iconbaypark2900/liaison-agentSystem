"""
reflexion_dspy — self-improving agent for liaison-agentSystem.

Combines:
  - DSPy  : structured LM programming + optimizer compilation
  - Reflexion : verbal RL through episodic reflection memory
  - MCP tools : 295+ tools across 31 servers via localhost gateway

Quick start:
  from reflexion_dspy.config import configure_dspy
  from reflexion_dspy.agent import ReflexionAgent

  configure_dspy()
  agent = ReflexionAgent()
  result = agent.forward("Search arxiv for quantum error correction papers")
  print(result.final_answer)
"""

from .agent import ReflexionAgent, AgentResult
from .config import configure_dspy
from .tools import MCPToolRegistry
from .memory import save_reflection, load_reflections, save_trace, load_all_traces
from .evaluator import default_evaluator, CompositeEvaluator
from .optimizer import compile_agent, trace_summary
from .coder import CodingAgent, CodingResult, write_coding_artifact
from .skills import SkillRouter, skill_router, route_task_skills, SkillRoutingResult
from .repl import ChatSession, ProjectContext

__all__ = [
    "ReflexionAgent",
    "AgentResult",
    "configure_dspy",
    "MCPToolRegistry",
    "save_reflection",
    "load_reflections",
    "save_trace",
    "load_all_traces",
    "default_evaluator",
    "CompositeEvaluator",
    "compile_agent",
    "trace_summary",
    "CodingAgent",
    "CodingResult",
    "write_coding_artifact",
    "SkillRouter",
    "skill_router",
    "route_task_skills",
    "SkillRoutingResult",
    "ChatSession",
    "ProjectContext",
]
