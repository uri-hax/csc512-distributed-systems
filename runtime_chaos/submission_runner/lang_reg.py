
LANGUAGES = {
    "python": {
        "extensions": [".py"],
        "compile": None,
        "run": lambda entry: ["python3", entry]
    },
    "c": {
        "extensions": [".c"],
        "compile": lambda sources, out: ["gcc", *sources, "-Wall", "-o", out],
        "run": lambda out: ["./" + out]
    },
    "cpp": {
        "extensions": [".cpp"],
        "compile": lambda sources, out: ["g++", *sources, "-Wall", "-std=c++17", "-o", out],
        "run": lambda out: ["./" + out]
    }
}
