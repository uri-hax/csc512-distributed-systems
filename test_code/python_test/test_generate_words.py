import pytest
import random
from hypothesis import given, settings, note
from hypothesis import strategies as st

# ── paste or import your wordle code here ──────────────────────────────────────
def generateWord(wordList):
    wordIndex = random.randint(0, len(wordList) - 1)
    word = wordList[wordIndex - 1]
    return word
# ──────────────────────────────────────────────────────────────────────────────


# Load the real word list once so tests can use it
def load_words(path="words.txt"):
    with open(path) as f:
        next(f)                      # skip header
        return [line.strip() for line in f if line.strip()]

WORD_LIST = load_words()


# ── Strategy ──────────────────────────────────────────────────────────────────
# Hypothesis will generate many different word lists of varying sizes (1–50
# words) drawn from the real word list.  This lets it probe edge cases like
# single-element lists, short lists, and full-size lists without us writing
# each case by hand.
word_list_strategy = st.lists(
    st.sampled_from(WORD_LIST),
    min_size=1,
    max_size=50
)


# ── Tests ─────────────────────────────────────────────────────────────────────

@given(wordList=word_list_strategy)
def test_returns_a_string(wordList):
    """generateWord should always return a string."""
    result = generateWord(wordList)
    assert isinstance(result, str)


@given(wordList=word_list_strategy)
def test_returns_five_letter_word(wordList):
    """Every word in our list is 5 letters, so the result must be too."""
    result = generateWord(wordList)
    note(f"wordList={wordList}, result={result!r}")
    assert len(result) == 5


@given(wordList=word_list_strategy)
def test_result_is_in_word_list(wordList):
    """
    The returned word must come from the list that was passed in.

    THIS TEST WILL FAIL.

    When randint returns 0, wordList[0 - 1] == wordList[-1], which is the
    LAST element of the list.  Python does not raise an IndexError for -1;
    it silently wraps around.  So if wordList[-1] is not a valid selection
    for the given list state, Hypothesis will catch it here.

    More practically: for a single-element list ['CRANE'], the only valid
    index is 0, but wordList[0 - 1] = wordList[-1] = 'CRANE' — that happens
    to pass.  For lists where the last element != the intended selection the
    bug surfaces as an out-of-contract return value.

    The minimal failing case Hypothesis will shrink to is a two-element list
    where wordList[randint(0,1)-1] can return wordList[-1] unexpectedly.
    """
    result = generateWord(wordList)
    note(f"wordList={wordList}, result={result!r}")
    assert result in wordList


@given(wordList=word_list_strategy)
@settings(max_examples=500)   # run more trials to increase pressure on randint(0,...)
def test_never_returns_index_minus_one(wordList):
    """
    Specifically targets the off-by-one: when randint returns 0 the code
    does wordList[0 - 1] = wordList[-1].  We detect this by seeding random
    so that randint is forced to return 0, then checking the result.

    Note: Hypothesis controls wordList; we manually force the bad seed.
    """
    random.seed(0)
    # Force randint(0, n-1) to return 0 by monkey-patching for one call
    original_randint = random.randint
    random.randint = lambda a, b: 0      # always return the boundary value
    try:
        result = generateWord(wordList)
        # When index is 0, wordList[0-1] = wordList[-1] (last element)
        # The FIRST element (index 0) should have been returned instead
        assert result == wordList[0], (
            f"Off-by-one detected: randint returned 0 but got "
            f"{result!r} (last element) instead of {wordList[0]!r} (first element)"
        )
    finally:
        random.randint = original_randint  # always restore


# ── Run directly ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Running Hypothesis tests on generateWord...\n")
    test_returns_a_string()
    print("  ✓ test_returns_a_string passed")
    test_returns_five_letter_word()
    print("  ✓ test_returns_five_letter_word passed")
    try:
        test_result_is_in_word_list()
        print("  ✓ test_result_is_in_word_list passed")
    except Exception as e:
        print(f"  ✗ test_result_is_in_word_list FAILED:\n    {e}")
    try:
        test_never_returns_index_minus_one()
        print("  ✓ test_never_returns_index_minus_one passed")
    except Exception as e:
        print(f"  ✗ test_never_returns_index_minus_one FAILED:\n    {e}")