"""The examples: each keeps its own copy of the simulator models it uses."""

from collections import defaultdict

from conftest import EXAMPLES


def test_the_copies_of_a_model_file_are_the_same():
    """A file in extensions/ of several examples (e.g. extensions/brian2/iaf_psc_exp.py)
    is the same file in each: a fix goes into every copy."""
    versions = defaultdict(dict)
    for path in EXAMPLES.glob("*/extensions/**/*.py"):
        example = path.relative_to(EXAMPLES).parts[0]
        versions[path.relative_to(EXAMPLES / example)][example] = path.read_text()

    differ = {str(name): sorted(copies) for name, copies in versions.items() if len(set(copies.values())) > 1}
    assert not differ, f"copies that differ, by example: {differ}"
