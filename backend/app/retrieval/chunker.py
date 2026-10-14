"""Semantic blocks, Unicode-safe bounded BPE chunks; overlap never drops source."""

import hashlib

from app.domain.documents import IngestError
from app.retrieval.tokenization import NAME, count

VERSION = "semantic-source-v1"


def prefix_end(value, budget):
    # Binary search character boundaries, then count the emitted substring exactly.
    lo, hi = 0, len(value)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count(value[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return lo


def chunks(parsed, stopped, target=600, maximum=900, overlap=80):
    if not 0 <= overlap < target <= maximum <= 900:
        raise IngestError("INVALID_CHUNK_CONFIGURATION")
    result = []
    for block in parsed["blocks"]:
        text, pos = block["text"], 0
        header = block.get("header", "")
        # Oversized headers are preserved in the source chunks, with a locator reference.
        repeat_header = header if count(header) < target // 2 else ""
        while pos < len(text):
            if stopped.is_set():
                raise IngestError("PARSE_STOPPED")
            prefix = repeat_header if pos and block["kind"] == "table" else ""
            budget = target - count(prefix)
            length = prefix_end(text[pos:], budget)
            if length < 1:
                raise IngestError("CHUNK_LIMIT")
            end = pos + length
            if end < len(text):
                boundary = text.rfind("\n", pos + length // 2, end)
                if boundary >= 0:
                    end = boundary + 1
            value = prefix + text[pos:end]
            while count(value) > maximum and end > pos:
                end -= 1
                value = prefix + text[pos:end]
            if end == pos:
                raise IngestError("CHUNK_LIMIT")
            locator = dict(
                block["locator"],
                char_start=block["char_start"] + pos,
                char_end=block["char_start"] + end,
                repeated_header=bool(prefix),
            )
            if header:
                locator["table_header"] = {"text": header, "oversized": not bool(repeat_header)}
            item = {
                k: block[k]
                for k in ["heading_path", "kind", "page_start", "page_end"]
                if k in block
            }
            item.update(
                text=value,
                text_hash=hashlib.sha256(value.encode()).hexdigest(),
                char_start=locator["char_start"],
                char_end=locator["char_end"],
                locator_json=locator,
                token_count=count(value),
                ordinal=len(result),
            )
            result.append(item)
            if end == len(text):
                break
            if block["kind"] == "table":
                pos = end  # Header is the table overlap, keep complete rows when possible.
            else:
                suffix = text[pos:end]
                # Find a bounded suffix; character-based search, real token measurement.
                n = min(len(suffix), overlap * 4)
                while n and count(suffix[-n:]) > overlap:
                    n -= 1
                pos = max(pos + 1, end - n)
    return dict(
        chunks=result,
        parser_version=parsed["parser_version"],
        chunker_version=VERSION,
        tokenizer=NAME,
        page_count=parsed["page_count"],
        page_issues=parsed["page_issues"],
    )
