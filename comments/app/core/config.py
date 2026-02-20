import re

#
# Scoring Dictionary Configuration
# 

WORD_RE = re.compile(r"\w+")
TRIVIAL = re.compile(r"^(?:increment|decrement|inc|dec|set|get|return|print|init|initialize|start|end|begin|end of|end-of)\b", re.I,)
STRUCTURAL = re.compile(r"\b(?:because|since|therefore|in order to|so that|ensures|algorithm|complexity|O\(|edge case|edge-case|boundary|assume|assumes|invariant|param|argument|return value|raises|throws|precondition|postcondition|contract)\b", re.I)
UNPROF = re.compile(r"\b(?:fuck|shit|damn|crap|wtf|stfu|lmao|lmfao|idiot|stupid|dumb|suck|hate|bitch|bloody)\b", re.I)
TODO_RE = re.compile(r"\b(?:todo|fixme|xxx|hack|tbd|to do)\b", re.I)
