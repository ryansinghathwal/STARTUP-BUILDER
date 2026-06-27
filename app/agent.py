# ruff: noqa
import os
import re
import json
import logging
import sys
import datetime
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.workflow import Workflow, START, Edge
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types

from .config import config

# Setup logger for security events
logger = logging.getLogger("startup_builder_security")
logging.basicConfig(level=logging.INFO)

# =====================================================================
# 1. Pydantic Schemas for Sub-Agents
# =====================================================================

class ConceptAnalysis(BaseModel):
    target_audience: str = Field(description="The primary demographic or target market.")
    key_features: list[str] = Field(description="List of 3 primary MVP features.")
    value_proposition: str = Field(description="Unique selling proposition.")

class MarketResearch(BaseModel):
    competitors: list[str] = Field(description="Top 2-3 competitors in the space.")
    market_size: str = Field(description="Estimated addressable market size (e.g. TAM).")
    risks: list[str] = Field(description="Top 2-3 regulatory, execution, or market risks.")

class LeanCanvas(BaseModel):
    problem: str = Field(description="Top 3 problems the startup addresses.")
    solution: str = Field(description="Proposed solutions for the problems.")
    key_metrics: str = Field(description="How success will be measured.")
    cost_structure: str = Field(description="Major costs for running the business.")
    revenue_streams: str = Field(description="How the startup will make money.")

class ProposalOutput(BaseModel):
    summary: str = Field(description="High-level pitch summary of the startup.")
    concept_analysis: ConceptAnalysis = Field(description="Concept analysis details.")
    market_research: MarketResearch = Field(description="Market research details.")
    lean_canvas: LeanCanvas = Field(description="Lean Canvas details.")

# =====================================================================
# 2. Specialized LlmAgents & Orchestrator
# =====================================================================

concept_analyst = LlmAgent(
    name="concept_analyst",
    model=Gemini(model=config.model),
    instruction="""You are an expert Startup Concept Analyst.
    Given a startup idea, analyze it and structure your analysis according to the ConceptAnalysis schema.
    Identify the key audience, the most critical 3 features for an MVP, and the core value proposition.
    """,
    output_schema=ConceptAnalysis,
    output_key="concept_analysis",
)

mcp_tools = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["app/mcp_server.py"],
        ),
    )
)

market_researcher = LlmAgent(
    name="market_researcher",
    model=Gemini(model=config.model),
    instruction="""You are an expert Startup Market Researcher.
    Analyze the competitor landscape, TAM (Total Addressable Market), and risks of the concept.
    Use the search_competitors tool to find active competitors in the vertical, and estimate_costs tool to estimate monthly burn rate.
    Return your findings structured according to the MarketResearch schema.
    """,
    tools=[mcp_tools],
    output_schema=MarketResearch,
    output_key="market_research",
)

canvas_generator = LlmAgent(
    name="canvas_generator",
    model=Gemini(model=config.model),
    instruction="""You are an expert Lean Canvas Designer.
    Construct a structured Lean Canvas covering: problems, solution, metrics, costs, and revenues.
    Use the generate_lean_canvas_template tool to get the baseline layout and structure suggestions.
    Return your findings structured according to the LeanCanvas schema.
    """,
    tools=[mcp_tools],
    output_schema=LeanCanvas,
    output_key="lean_canvas",
)

orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model=config.model),
    instruction="""You are the StartupBuilder Orchestrator.
    Your task is to coordinate the validation and planning of the startup idea: {startup_idea}.
    If the user has provided feedback for refinement, incorporate it: {refinement_feedback}.

    Perform these actions in order:
    1. Delegate to concept_analyst to analyze the core idea concept.
    2. Delegate to market_researcher to investigate the market and risks.
    3. Delegate to canvas_generator to create the Lean Canvas.

    Synthesize all their findings and generate a cohesive final proposal matching the ProposalOutput schema.
    """,
    tools=[
        AgentTool(concept_analyst),
        AgentTool(market_researcher),
        AgentTool(canvas_generator),
    ],
    output_schema=ProposalOutput,
    output_key="proposal",
)

# =====================================================================
# 3. Workflow Function Nodes
# =====================================================================

def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    """Checks input for PII, prompt injection attacks, and prohibited business verticals."""
    input_text = ""
    if hasattr(node_input, 'parts') and node_input.parts:
        input_text = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, str):
        input_text = node_input

    # 1. PII Scrubbing (Regex for emails and phone numbers)
    scrubbed = input_text
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_regex = r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}"
    
    scrubbed = re.sub(email_regex, "[EMAIL_REDACTED]", scrubbed)
    scrubbed = re.sub(phone_regex, "[PHONE_REDACTED]", scrubbed)

    # 2. Prompt Injection Detection (Keyword Checks)
    injection_keywords = ["ignore previous instructions", "system prompt", "dan mode", "you must now act as"]
    injection_detected = any(keyword in input_text.lower() for keyword in injection_keywords)

    # 3. Prohibited Niche Filter (Domain-Specific Security Rule)
    prohibited_keywords = ["gambling", "casino", "marijuana", "weed", "weapons", "drugs", "illegal"]
    prohibited_detected = any(keyword in input_text.lower() for keyword in prohibited_keywords)

    # 4. Structured Audit Log
    severity = "INFO"
    if injection_detected:
        severity = "CRITICAL"
    elif prohibited_detected or scrubbed != input_text:
        severity = "WARNING"

    audit_log = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "severity": severity,
        "event": "input_security_check",
        "pii_detected": scrubbed != input_text,
        "injection_detected": injection_detected,
        "prohibited_vertical_detected": prohibited_detected,
    }
    logger.info(json.dumps(audit_log))

    if injection_detected:
        return Event(output="Block", route="fail", state={"security_block_reason": "injection"})
    elif prohibited_detected:
        return Event(output="Block", route="fail", state={"security_block_reason": "prohibited_content"})
    
    return Event(
        output=scrubbed,
        route="pass",
        state={
            "startup_idea": scrubbed,
            "refinement_feedback": "",
        }
    )

def security_event(ctx: Context, node_input: str) -> Event:
    """Handles security violations by routing and notifying the user."""
    reason = ctx.state.get("security_block_reason", "injection")
    if reason == "prohibited_content":
        msg = "❌ Input blocked: StartupBuilder does not support building businesses in prohibited/harmful verticals (e.g., gambling, weapons, drugs)."
    else:
        msg = "❌ Input blocked: Potential prompt injection detected. Please submit a valid startup idea."

    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=msg)]
        )
    )
    yield Event(output={"error": "Security policy violation."})

async def human_review(ctx: Context, node_input: dict):
    """Asks the user for approval or feedback in a human-in-the-loop step."""
    summary = node_input.get("summary", "")
    concept = node_input.get("concept_analysis", {})
    market = node_input.get("market_research", {})
    canvas = node_input.get("lean_canvas", {})

    if not ctx.resume_inputs:
        msg = f"""Here is your Startup Proposal:
        
**Summary:** {summary}

**Concept Analysis:**
- Target Audience: {concept.get('target_audience', '')}
- Key Features: {', '.join(concept.get('key_features', []))}
- Value Proposition: {concept.get('value_proposition', '')}

**Market Research:**
- Competitors: {', '.join(market.get('competitors', []))}
- Market Size: {market.get('market_size', '')}
- Risks: {', '.join(market.get('risks', []))}

**Lean Canvas:**
- Problem: {canvas.get('problem', '')}
- Solution: {canvas.get('solution', '')}
- Key Metrics: {canvas.get('key_metrics', '')}
- Cost Structure: {canvas.get('cost_structure', '')}
- Revenue Streams: {canvas.get('revenue_streams', '')}

Do you approve this proposal? Enter 'approve' to finalize, or describe your requested refinements:
"""
        yield RequestInput(interrupt_id="approval_or_feedback", message=msg)
        return

    user_input = ctx.resume_inputs.get("approval_or_feedback", "").strip()
    if user_input.lower() == "approve":
        yield Event(output=node_input, route="approve")
    else:
        yield Event(
            output=user_input,
            route="refine",
            state={"refinement_feedback": user_input}
        )

def final_output(node_input: dict) -> Event:
    """Emits the final summary to the user."""
    summary = node_input.get("summary", "")
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=f"✅ Startup proposal approved!\n\nSummary:\n{summary}")]
        )
    )
    yield Event(output=node_input)

# =====================================================================
# 4. Workflow Edges & Initialization
# =====================================================================

root_agent = Workflow(
    name="startup_builder_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"pass": orchestrator, "fail": security_event}),
        (orchestrator, human_review),
        (human_review, {"refine": orchestrator, "approve": final_output}),
        (security_event, final_output),
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True)
)
