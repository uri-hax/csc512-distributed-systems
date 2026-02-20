import os

def system_status():
    branch = os.environ.get("BRANCH")
    return { "Service": "Comment Analyzer", "Branch": branch, "Status": "OK" }
