from typing import Optional
from pydantic import BaseModel

#
# Structures for API requests/responses
#

class AnalyzeRequest(BaseModel):
    submission_id: Optional[str] = None

#
# Enumerations
#

LANG_TO_COMMENT_TOKENS = {
    '.py': {'line': ['#'], 'block': []},
    '.js': {'line': ['//'], 'block': [('/*','*/')]},
    '.java': {'line': ['//'], 'block': [('/*','*/')]},
    '.c': {'line': ['//'], 'block': [('/*','*/')]},
    '.cpp': {'line': ['//'], 'block': [('/*','*/')]},
    '.h': {'line': ['//'], 'block': [('/*','*/')]},
    '.rs': {'line': ['///', '//!', '//'], 'block': [('/*','*/')]},
    '.go': {'line': ['//'], 'block': [('/*','*/')]},
    '.sh': {'line': ['#'], 'block': []},
    '.bash': {'line': ['#'], 'block': []},
    '.ts': {'line': ['//'], 'block': [('/*','*/')]},
}
