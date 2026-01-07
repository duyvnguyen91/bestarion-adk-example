import os
import requests
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

MODEL = LiteLlm("ollama/gemma3")

JENKINS_URL = os.environ.get("JENKINS_URL", "http://localhost:8080")
JENKINS_USER = os.environ.get("JENKINS_USER", "admin")
JENKINS_API_TOKEN = os.environ.get("JENKINS_API_TOKEN", "11d51b2afa6a93663e667203e558b60a09")

def create_pipeline_job(
    job_name: str,
    message: str
) -> dict:
    """
    Create a simple Jenkins pipeline job with one stage printing a message.
    """

    pipeline_xml = f"""
    <flow-definition plugin="workflow-job">
    <description>Pipeline created by ADK agent</description>
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps">
        <script>
    pipeline {{
    agent any
    stages {{
        stage('Hello') {{
        steps {{
            echo '{message}'
        }}
        }}
    }}
    }}
        </script>
        <sandbox>true</sandbox>
    </definition>
    </flow-definition>
    """.strip()

    url = f"{JENKINS_URL}/createItem"
    params = {"name": job_name}

    headers = {"Content-Type": "application/xml"}

    resp = requests.post(
        url,
        params=params,
        data=pipeline_xml,
        headers=headers,
        auth=(JENKINS_USER, JENKINS_API_TOKEN),
        timeout=10,
    )

    if resp.status_code == 200:
        return {
            "status": "success",
            "message": f"Pipeline '{job_name}' created successfully"
        }

    if resp.status_code == 400:
        return {
            "status": "error",
            "error_message": f"Pipeline '{job_name}' already exists"
        }

    return {
        "status": "error",
        "error_message": f"Failed to create pipeline '{job_name}' (HTTP {resp.status_code})"
    }


root_agent = Agent(
    name="JenkinsPipelineCreator",
    model=MODEL,
    tools=[create_pipeline_job],
    description="Creates simple Jenkins pipeline jobs",
    instruction="""
    You are a Jenkins pipeline creation assistant.

    IMPORTANT RULES (MUST FOLLOW):
    - You have EXACTLY ONE tool available: create_pipeline_job
    - NEVER invent or guess tool names
    - If a pipeline needs to be created, you MUST call create_pipeline_job
    - You MUST NEVER use placeholders like "function_name".
    - The tool arguments are:
    - job_name (string, required)
    - message (string, optional, default: "Hello World")
    - Do NOT call any other tool
    - Do NOT trigger the pipeline after creation
    - Do NOT describe Jenkins XML unless asked

    When the user asks to create a pipeline:
    1. Determine the pipeline name
    2. Call create_pipeline_job with that name
    3. Confirm creation in plain text
    4. Do not invent tool names

    If the pipeline name is missing:
    - Ask the user for the pipeline name
    - DO NOT call the tool yet

    AFTER a successful tool call:
    - You MUST respond with a clear confirmation message like a senior DevOps engineer.
    - you MUST reply with PLAIN TEXT
    - Include:
        - Pipeline name
        - What the pipeline does
        - That it was NOT triggered

    Tool schema:
    - create_pipeline_job(job_name: string, message: string)
    """,
)
