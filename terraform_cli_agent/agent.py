import json
import sys
from typing import Dict
from pathlib import Path
from google import adk
from google.adk.agents import Agent, SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# AGENT_MODEL = "ollama/qwen2.5:7b"  # For local LLM
AGENT_MODEL = "gemini-2.0-flash"

class TerraformPlanData:
    """Singleton class to hold terraform plan data"""
    _instance = None
    _data = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_data(self, data: Dict):
        self._data = data
    
    def get_data(self) -> Dict:
        return self._data

# Create singleton instance
tfplan_store = TerraformPlanData()

def summarize_plan() -> str:
    """Summarize Terraform plan changes.
    
    Returns a human-readable summary of the plan changes.
    """
    TFPLAN_DATA = tfplan_store.get_data()
    
    if not TFPLAN_DATA:
        return "Error: No Terraform plan data available. The tfplan.json file may not have been loaded correctly."

    resource_changes = TFPLAN_DATA.get("resource_changes", [])
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
        "Terraform Plan Summary:",
        "",
        "Total Changes:",
        f"  - Create: {create_count} resources",
        f"  - Update: {update_count} resources",
        f"  - Delete: {delete_count} resources",
        "",
    ]

    if resource_types:
        summary_parts.append("Resource Types Affected:")
        for res_type, count in sorted(resource_types.items()):
            summary_parts.append(f"  - {res_type}: {count}")

    summary_parts.append("")
    summary_parts.append("Resources:")
    for res in resources_list[:20]:  # Limit to first 20 for readability
        actions_str = ", ".join(res["actions"])
        summary_parts.append(f"  - {res['address']} ({res['type']}): {actions_str}")
    
    if len(resources_list) > 20:
        summary_parts.append(f"  ... and {len(resources_list) - 20} more resources")

    return "\n".join(summary_parts)

def security_compliance_scan() -> str:
    """Perform security compliance scan on Terraform plan.
    
    Scans for security and compliance issues.
    Returns a formatted security report with findings.
    """
    TFPLAN_DATA = tfplan_store.get_data()
    
    if not TFPLAN_DATA:
        return "ERROR: No Terraform plan data available. The tfplan.json file may not have been loaded correctly.\nCannot perform security scan."

    findings = []
    resource_changes = TFPLAN_DATA.get("resource_changes", [])

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

def test_data_access() -> str:
    """Test function to verify data is accessible"""
    data = tfplan_store.get_data()
    if data:
        return f"SUCCESS: Data is accessible. Found {len(data.get('resource_changes', []))} resource changes."
    else:
        return "FAILURE: Data is not accessible."

if __name__ == "__main__":
    if "--input" not in sys.argv:
        print("Usage: python3 agent.py --input tfplan.json")
        sys.exit(1)

    tfplan_path = sys.argv[sys.argv.index("--input") + 1]
    
    # Load the tfplan file content into singleton
    try:
        tfplan_file = Path(tfplan_path)
        if not tfplan_file.exists():
            print(f"Error: File not found: {tfplan_path}")
            sys.exit(1)
            
        with open(tfplan_file, "r", encoding="utf-8") as f:
            tfplan_data = json.load(f)
        
        # Verify it's a valid Terraform plan
        if "resource_changes" not in tfplan_data:
            print("Warning: This doesn't appear to be a valid Terraform plan JSON file.")
            print("Expected 'resource_changes' key not found.")
            sys.exit(1)
        
        # Store in singleton
        tfplan_store.set_data(tfplan_data)
            
        print(f"✓ Successfully loaded Terraform plan from {tfplan_path}")
        print(f"✓ Found {len(tfplan_data.get('resource_changes', []))} resource changes")
        
        # Test that data is accessible
        test_result = test_data_access()
        print(f"✓ Data access test: {test_result}")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in tfplan file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading tfplan.json: {e}")
        sys.exit(1)

    # Create agents (tools are defined above and should have access to tfplan_store)
    plan_summarization_agent = Agent(
        name="TerraformPlanSummarizer",
        model=AGENT_MODEL,
        tools=[summarize_plan],
        output_key="plan_summary",
        description="Summarizes Terraform plan changes",
        instruction="""
        You are a Terraform Infrastructure Analyst.

        TASK: Provide a clear, readable summary of the Terraform plan for the developer.

        WORKFLOW:
        1. Call the summarize_plan tool to get the plan summary
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
        tools=[security_compliance_scan],
        description="Performs security & compliance checks",
        instruction="""You are a Senior DevOps Security Engineer conducting a security review.

        CRITICAL WORKFLOW:
        1. Call security_compliance_scan tool ONCE to get the security scan results
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

    # Initialize session service and runner
    session_service = InMemorySessionService()
    runner = adk.Runner(
        agent=root_agent,
        app_name="terraform_cli_agent",
        session_service=session_service
    )
    
    # Create a session
    import asyncio
    session = asyncio.run(session_service.create_session(
        app_name="terraform_cli_agent",
        user_id="cli_user",
        session_id="session_1"
    ))
    
    # Create the user message requesting analysis
    user_message = Content(parts=[Part(text="Please analyze the Terraform plan that has been loaded.")])
    
    print("\n" + "="*60)
    print("Starting Terraform Plan Analysis")
    print("="*60 + "\n")
    
    # Run the agent and collect output
    try:
        for event in runner.run(user_id="cli_user", session_id="session_1", new_message=user_message):
            if event.is_final_response():
                print("\n" + "="*60)
                print("Analysis Complete")
                print("="*60 + "\n")
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text'):
                            print(part.text)
                else:
                    print(event.content)
    except Exception as e:
        print(f"\n❌ Error during agent execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)