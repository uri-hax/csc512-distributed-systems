import os

def system_status():
    branch, llm_model = os.environ.get("BRANCH"), os.environ.get("LLM_MODEL")
    return { "Service": "Comment Analyzer", "Model": llm_model, "Branch": branch }
