from kb_rag import NOT_IN_DOCS, SearchResult


def cited_sources(found: SearchResult) -> list[str]:
    sources: list[str] = []
    for passage in found.passages:
        if passage.source not in sources:
            sources.append(passage.source)
    return sources


def tool_text(found: SearchResult) -> str:
    if found.abstained:
        return f"not in the docs. Say exactly: {NOT_IN_DOCS} Do not invent an answer."
    passages = [
        f"[{index}] source: {passage.source}\n{passage.text}"
        for index, passage in enumerate(found.passages, start=1)
    ]
    return (
        "Use only these passages. Do not add facts that are not written here.\n"
        + "\n\n".join(passages)
    )


def citation_suffix(sources: list[str]) -> str:
    return "".join(f"\nSource: {source}" for source in sources)


def retrieval_record(product_id: str, found: SearchResult) -> dict[str, object]:
    return {
        "kind": "retrieval",
        "product_id": product_id,
        "duration_ms": round(found.timings_ms["total"]),
        "hit_count": len(found.passages),
        "abstained": found.abstained,
    }
