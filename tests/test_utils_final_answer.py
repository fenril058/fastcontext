from fastcontext.agent.utils import get_final_answer, parse_citations

_REAL_FILE = __file__


def _wrap(body: str) -> str:
    return f"<final_answer>\n{body}\n</final_answer>"


def test_single_citation_no_explanation():
    text = _wrap(f"{_REAL_FILE}:1")
    result = get_final_answer(text)
    assert f"{_REAL_FILE}:1" in result
    print(result)


def test_single_citation_with_line_range():
    text = _wrap(f"{_REAL_FILE}:1-5")
    result = get_final_answer(text)
    print(result)
    assert f"{_REAL_FILE}:1-5" in result


def test_multiple_citations():
    text = _wrap(f"{_REAL_FILE}:1-3 (first)\n" f"{_REAL_FILE}:5 (second)")
    result = get_final_answer(text)
    print(result)
    assert f"{_REAL_FILE}:1-3 (first)" in result
    assert f"{_REAL_FILE}:5 (second)" in result


def test_surrounding_text_is_ignored():
    text = f"some preamble\n{_wrap(f'{_REAL_FILE}:1')}\nsome postamble"
    result = get_final_answer(text)
    print(result)
    assert f"{_REAL_FILE}:1" in result
    assert "preamble" not in result
    assert "postamble" not in result


def test_blank_lines_inside_tags_are_skipped():
    text = _wrap(f"\n\n{_REAL_FILE}:1\n\n")
    result = get_final_answer(text)
    print(result)
    assert f"{_REAL_FILE}:1" in result


def test_mix_valid_and_invalid_files():
    text = _wrap(f"{_REAL_FILE}:1 (kept)\n" "/nonexistent/file.py:2 (dropped)")
    result = get_final_answer(text)
    print(result)
    assert f"{_REAL_FILE}:1 (kept)" in result
    assert "/nonexistent/file.py" not in result


def test_missing_final_answer_block_returns_the_text():
    text = "I could not find anything relevant."
    assert get_final_answer(text) == text


def test_missing_final_answer_block_is_stripped():
    assert get_final_answer("  no block here  \n") == "no block here"


def test_empty_content_is_tolerated():
    # Agent.run passes Message.content straight through, and it is None when
    # the model emits only reasoning.
    assert get_final_answer(None) == ""
    assert get_final_answer("") == ""


def test_parse_citations_always_returns_a_list():
    assert parse_citations("no block here") == []
    assert parse_citations(_wrap("not a citation line")) == []
    assert isinstance(parse_citations(_wrap(f"{_REAL_FILE}:1")), list)


if __name__ == "__main__":
    test_single_citation_no_explanation()
    test_single_citation_with_line_range()
    test_multiple_citations()
    test_surrounding_text_is_ignored()
    test_blank_lines_inside_tags_are_skipped()
    test_mix_valid_and_invalid_files()
