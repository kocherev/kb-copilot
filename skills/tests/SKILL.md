# Tests

Assert what a caller can observe. Status codes, response bodies, rendered text, link targets, and rejected input are observable. A test that restates the current function body will stay green after a silent behavior change.

When the behavior is local and cheap, write the assertion first. Run it. Confirm it fails for the reason you expect. Then change the code and rerun it.

Do not weaken an assertion to match a wrong result.

Do not add a test that only checks a mock, a timer, or `True`.
