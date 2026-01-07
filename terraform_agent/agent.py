import json
from typing import TYPE_CHECKING, Dict, List

from google.adk.agents import Agent, SequentialAgent
# from google.adk.models.lite_llm import LiteLlm
from google.adk.apps import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.adk.tools.tool_context import ToolContext

# AGENT_MODEL = LiteLlm("ollama/qwen2.5:7b")
AGENT_MODEL = "gemini-2.0-flash"

async def _load_tfplan(tool_context: "ToolContext") -> Dict:
    """Load tfplan.json from artifacts."""
    # First, list available artifacts to help with debugging
    available = await tool_context.list_artifacts()
    
    # Try to load the artifact
    artifact = await tool_context.load_artifact("tfplan.json")
    
    if artifact is None:
        # Try with user: prefix for cross-session artifacts
        artifact = await tool_context.load_artifact("user:tfplan.json")
    
    if artifact is None:
        raise FileNotFoundError(
            f"tfplan.json not found. Available artifacts: {available}"
        )
    
    # Extract JSON data from the artifact Part
    # The artifact can be in different formats (inline_data, file_data, text)
    try:
        if hasattr(artifact, 'inline_data') and artifact.inline_data:
            data = artifact.inline_data.data
            if isinstance(data, bytes):
                return json.loads(data.decode('utf-8'))
            elif isinstance(data, str):
                return json.loads(data)
        elif hasattr(artifact, 'file_data') and artifact.file_data:
            # For file_data, read from the file URI
            file_uri = artifact.file_data.file_uri
            if file_uri:
                # If it's a local file path, read it directly
                if file_uri.startswith('file://'):
                    import urllib.parse
                    file_path = urllib.parse.unquote(file_uri.replace('file://', ''))
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    raise ValueError(f"Unsupported file URI format: {file_uri}")
            else:
                raise ValueError("File data artifact has no file_uri")
        elif hasattr(artifact, 'text') and artifact.text:
            return json.loads(artifact.text)
        else:
            # Try to get text representation as fallback
            artifact_str = str(artifact)
            if artifact_str:
                return json.loads(artifact_str)
            raise ValueError(f"Unable to extract JSON from artifact. Artifact type: {type(artifact)}, attributes: {dir(artifact)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from artifact: {e}")
    except Exception as e:
        raise ValueError(f"Error loading artifact: {e}")


async def summarize_plan_from_artifact(tool_context: "ToolContext") -> Dict:
    """Summarize Terraform plan from artifact.
    
    Loads tfplan.json and returns a human-readable summary of the plan changes.
    This tool is ONLY for summarizing - do NOT use it for security scanning.
    """
    try:
        tfplan = await _load_tfplan(tool_context)
    except Exception as e:
        return f"Error: Failed to load tfplan.json: {str(e)}"

    resource_changes = tfplan.get("resource_changes", [])
    if not resource_changes:
        return "No resource changes found in the Terraform plan."

    create_count = 0
    update_count = 0
    delete_count = 0
    resource_types = {}
    resources_list = []

    for r in resource_changes:
        change = r.get("change", {})
        actions = change.get("actions", [])
        res_type = r.get("type", "unknown")
        address = r.get("address", "unknown")

        if "create" in actions:
            create_count += 1
        if "update" in actions:
            update_count += 1
        if "delete" in actions:
            delete_count += 1

        resource_types[res_type] = resource_types.get(res_type, 0) + 1
        resources_list.append({
            "address": address,
            "type": res_type,
            "actions": actions,
        })

    # Build a readable summary
    summary_parts = [
        f"Terraform Plan Summary:",
        f"",
        f"Total Changes:",
        f"  - Create: {create_count} resources",
        f"  - Update: {update_count} resources",
        f"  - Delete: {delete_count} resources",
        f"",
    ]

    if resource_types:
        summary_parts.append(f"Resource Types Affected:")
        for res_type, count in sorted(resource_types.items()):
            summary_parts.append(f"  - {res_type}: {count}")

    summary_parts.append(f"")
    summary_parts.append(f"Resources:")
    for res in resources_list[:20]:  # Limit to first 20 for readability
        actions_str = ", ".join(res["actions"])
        summary_parts.append(f"  - {res['address']} ({res['type']}): {actions_str}")
    
    if len(resources_list) > 20:
        summary_parts.append(f"  ... and {len(resources_list) - 20} more resources")

    return "\n".join(summary_parts)

async def security_compliance_scan_from_artifact(tool_context: "ToolContext") -> Dict:
    """Perform security compliance scan on Terraform plan from artifact.
    
    Loads tfplan.json and scans for security and compliance issues.
    This tool is ONLY for security scanning - do NOT use it for summarizing.
    Returns a formatted security report with findings.
    """
    try:
        tfplan = await _load_tfplan(tool_context)
    except Exception as e:
        return f"ERROR: Failed to load tfplan.json: {str(e)}\nCannot perform security scan."

    findings = []
    resource_changes = tfplan.get("resource_changes", [])

    for r in resource_changes:
        res_type = r.get("type", "")
        change = r.get("change", {})
        after = change.get("after") or {}
        resource_address = r.get("address", "unknown")

        if res_type == "google_container_cluster":
            master_config = after.get("master_authorized_networks_config")
            if master_config:
                # Handle both list and dict formats
                if isinstance(master_config, list):
                    for m in master_config:
                        cidr_blocks = m.get("cidr_blocks", [])
                        for cidr in cidr_blocks:
                            if isinstance(cidr, dict) and cidr.get("cidr_block") == "0.0.0.0/0":
                                findings.append({
                                    "severity": "HIGH",
                                    "resource": resource_address,
                                    "issue": "GKE control plane is publicly accessible",
                                    "impact": "Kubernetes API exposed to the internet",
                                })
                                break
                elif isinstance(master_config, dict):
                    cidr_blocks = master_config.get("cidr_blocks", [])
                    for cidr in cidr_blocks:
                        if isinstance(cidr, dict) and cidr.get("cidr_block") == "0.0.0.0/0":
                            findings.append({
                                "severity": "HIGH",
                                "resource": resource_address,
                                "issue": "GKE control plane is publicly accessible",
                                "impact": "Kubernetes API exposed to the internet",
                            })
                            break

        if res_type == "google_sql_database_instance":
            if after.get("deletion_protection") is False:
                findings.append({
                    "severity": "MEDIUM",
                    "resource": resource_address,
                    "issue": "CloudSQL deletion protection disabled",
                    "impact": "Risk of accidental deletion",
                })

        if res_type == "kubernetes_secret":
            findings.append({
                "severity": "LOW",
                "resource": resource_address,
                "issue": "Kubernetes secret created",
                "impact": "Ensure encryption and RBAC restrictions",
            })

    # Format findings as a readable report
    if not findings:
        return "Security Scan Results:\n\nNo security issues found in the Terraform plan."

    # Group by severity
    high_findings = [f for f in findings if f["severity"] == "HIGH"]
    medium_findings = [f for f in findings if f["severity"] == "MEDIUM"]
    low_findings = [f for f in findings if f["severity"] == "LOW"]

    report_parts = [
        "Security & Compliance Scan Report",
        "=" * 50,
        "",
        f"Summary: {len(high_findings)} HIGH, {len(medium_findings)} MEDIUM, {len(low_findings)} LOW severity findings",
        "",
    ]

    if high_findings:
        report_parts.append("HIGH SEVERITY FINDINGS:")
        report_parts.append("-" * 50)
        for finding in high_findings:
            report_parts.append(f"Resource: {finding['resource']}")
            report_parts.append(f"Issue: {finding['issue']}")
            report_parts.append(f"Impact: {finding['impact']}")
            report_parts.append("")

    if medium_findings:
        report_parts.append("MEDIUM SEVERITY FINDINGS:")
        report_parts.append("-" * 50)
        for finding in medium_findings:
            report_parts.append(f"Resource: {finding['resource']}")
            report_parts.append(f"Issue: {finding['issue']}")
            report_parts.append(f"Impact: {finding['impact']}")
            report_parts.append("")

    if low_findings:
        report_parts.append("LOW SEVERITY FINDINGS:")
        report_parts.append("-" * 50)
        for finding in low_findings:
            report_parts.append(f"Resource: {finding['resource']}")
            report_parts.append(f"Issue: {finding['issue']}")
            report_parts.append(f"Impact: {finding['impact']}")
            report_parts.append("")

    return "\n".join(report_parts)

plan_summarization_agent = Agent(
    name="TerraformPlanSummarizer",
    model=AGENT_MODEL,
    tools=[summarize_plan_from_artifact],
    output_key="plan_summary",
    description="Summarizes Terraform plan changes",
    instruction="""
    You are a Terraform Infrastructure Analyst.

    TASK: Provide a clear, readable summary of the Terraform plan for the developer.

    WORKFLOW:
    1. Call the summarize_plan_from_artifact tool to get the plan summary
    2. Present the results in a well-formatted, markdown response for the user
    3. Speak directly to the developer with clear explanations

    OUTPUT FORMAT:
    - Use markdown headers (##, ###)
    - Use bullet points and formatting
    - Be concise but informative
    - Do NOT output raw JSON or tool data

    Example:
    ## 📊 Terraform Plan Summary

    **Total Changes:** 22 resources
    - ✅ Create: 20 resources  
    - 🔄 Update: 2 resources
    - ❌ Delete: 0 resources

    [Continue with details...]
    """,
)

security_agent = Agent(
    name="TerraformSecurityReviewer",
    model=AGENT_MODEL,
    tools=[security_compliance_scan_from_artifact],
    description="Performs security & compliance checks - ONLY use security_compliance_scan_from_artifact tool",
    instruction="""You are a Senior DevOps Security Engineer conducting a security review.

    CRITICAL WORKFLOW:
    1. Call security_compliance_scan_from_artifact tool ONCE to get the security scan results
    2. Take the tool output and present it to the user in a professional, readable format
    3. Add context and recommendations where helpful
    4. STOP after presenting the report - do NOT call tools again

    OUTPUT REQUIREMENTS:
    - Use markdown formatting with headers and sections
    - Highlight severity levels with emojis or formatting
    - Provide actionable recommendations
    - Speak directly to the developer
    - Do NOT output raw JSON or echo tool responses verbatim

    Example Structure:
    ## 🔒 Security & Compliance Review

    ### Summary
    Found X issues across Y resources...

    ### 🔴 Critical Issues
    1. **Resource**: ...
    **Issue**: ...

    [Continue with organized sections...]
    
    ### 👍 Recommendations
    [Provide actionable recommendations here]
    """,
)


root_agent = SequentialAgent(
    name="TerraformPlanReviewSystem",
    sub_agents=[
        plan_summarization_agent,
        security_agent,
    ],
)

app = App(
    name="terraform_agent",
    root_agent=root_agent,
    plugins=[SaveFilesAsArtifactsPlugin()],
)
