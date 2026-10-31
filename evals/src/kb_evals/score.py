def exact_match(expected: str, actual: str) -> float:
    if expected == actual:
        return 1.0
    return 0.0
