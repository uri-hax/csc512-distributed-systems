from .detect import get_files, detect_language, detect_build_system
from .build_systems import build_with_make, build_with_bash, default_language_build
from .lang_reg import LANGUAGES
import os

 
def build_submission(submission):
    build_system = detect_build_system(submission)

    if build_system == "make":
        return build_with_make(submission)
    elif build_system == "script":
        return build_with_bash(submission)
    else:
        lang = detect_language(submission)
        cfg = LANGUAGES[lang]

        relevant_files = get_files(submission)

        sources = [
            f for f in relevant_files
            if os.path.splitext(f)[1] in cfg["extensions"]
        ]
        return default_language_build(submission, sources,cfg)
