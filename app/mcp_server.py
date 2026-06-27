import sys
from mcp.server.fastmcp import FastMCP

# Create the FastMCP server instance
mcp = FastMCP("StartupBuilderMCP")

@mcp.tool()
def search_competitors(industry: str) -> str:
    """Search for top competitors in a given startup industry.
    
    Args:
        industry: The vertical or industry name (e.g. AI, FinTech, EdTech).
        
    Returns:
        A text report of typical market competitors and their positioning.
    """
    industry_lower = industry.lower()
    if "ai" in industry_lower or "artificial intelligence" in industry_lower:
        return (
            "Competitors in AI Space:\n"
            "1. OpenAI - Leader in foundational models, high brand equity, massive API developer base.\n"
            "2. Anthropic - Focus on safety and large context windows (Claude).\n"
            "3. Cohere - Focus on enterprise search and RAG integrations."
        )
    elif "fintech" in industry_lower or "finance" in industry_lower:
        return (
            "Competitors in FinTech Space:\n"
            "1. Stripe - Leader in online payments infrastructure and API developer experience.\n"
            "2. Adyen - Enterprise-focused payment processing platform.\n"
            "3. Plaid - Account aggregation API connecting bank accounts to apps."
        )
    elif "health" in industry_lower or "medical" in industry_lower:
        return (
            "Competitors in HealthTech Space:\n"
            "1. Oscar Health - Modern tech-driven consumer health insurance.\n"
            "2. Flatiron Health - Oncology-focused electronic health records and clinical data.\n"
            "3. Tempus - Data-driven precision medicine and clinical trials matching."
        )
    else:
        return (
            f"Competitors in the general {industry} field:\n"
            f"1. BigCo Inc. - Well-established incumbent with legacy software.\n"
            f"2. QuickStart Ltd - Fast-growing venture-backed startup in seed stage.\n"
            f"3. OpenSolution - Open-source alternative gaining developer interest."
        )

@mcp.tool()
def estimate_costs(industry: str, team_size: int) -> str:
    """Estimate key launch and monthly operational costs for a startup based on industry and team size.
    
    Args:
        industry: The vertical or industry name (e.g. AI, SaaS, hardware).
        team_size: Number of planned founding team members/initial hires.
        
    Returns:
        A structured breakdown of monthly cost estimations.
    """
    salary_per_member = 8000  # monthly estimate
    hosting_costs = 200
    if "ai" in industry.lower():
        hosting_costs = 2500  # high GPU cost
    elif "hardware" in industry.lower():
        hosting_costs = 500
        
    salary_total = team_size * salary_per_member
    legal_setup = 1500
    total_monthly = salary_total + hosting_costs + 500  # + miscellaneous
    
    return (
        f"--- Cost Estimate Breakdown ({industry} startup, {team_size} members) ---\n"
        f"• Founding/Team Salaries: ${salary_total:,}/month (avg ${salary_per_member}/member)\n"
        f"• Infrastructure / Hosting: ${hosting_costs:,}/month\n"
        f"• Legal/Incorporation (One-time): ${legal_setup:,}\n"
        f"• Miscellaneous/Office/Tools: $500/month\n"
        f"-----------------------------------------\n"
        f"Estimated Total Monthly Burn Rate: ${total_monthly:,}/month"
    )

@mcp.tool()
def generate_lean_canvas_template() -> str:
    """Generate the standard markdown skeleton for a Lean Canvas.
    
    Returns:
        Markdown string containing a blank Lean Canvas table/structure.
    """
    return (
        "| Problem | Solution | Unique Value Prop | Unfair Advantage | Customer Segments |\n"
        "| :--- | :--- | :--- | :--- | :--- |\n"
        "| Top 3 problems to solve | MVP features solving problems | Compelling message why you differ | Something that cannot be easily copied | Target customers and early adopters |\n"
        "| **Existing Alternatives** | | **High-Level Concept** | | **Early Adopters** |\n"
        "| Competitors in the space | | X for Y analogy | | Ideal first users |\n"
        "\n"
        "| Key Metrics | Cost Structure | Revenue Streams | Channels |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| Key activities you measure | Burn rate, host costs, salaries | Pricing, margins, recurring rev | Paths to customers |"
    )

if __name__ == "__main__":
    mcp.run()
