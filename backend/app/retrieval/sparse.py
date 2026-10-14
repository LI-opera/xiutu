"""Deterministic small-corpus TF-IDF, preserving full diagnostic codes."""

import math
import re
from collections import Counter

DTC = re.compile(r"(?<![A-Z0-9])[PBCU][0-9A-F]{4,6}(?![A-Z0-9])", re.I)


def codes(text):
    return set(x.upper() for x in DTC.findall(text))


def tokens(text):
    parts = re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]+", text.casefold())
    result = []
    for part in parts:
        if "\u3400" <= part[0] <= "\u9fff":
            result.extend(part)
            result.extend(part[i : i + 2] for i in range(len(part) - 1))
        else:
            result.append(part)
    return result


def rank(query, documents):
    counts = [Counter(tokens(x)) for x in documents]
    df = Counter(t for count in counts for t in count)
    n = len(documents)

    def vector(count):
        values = {
            t: (1 + math.log(v)) * (math.log((n + 1) / (df[t] + 1)) + 1) for t, v in count.items()
        }
        norm = math.sqrt(sum(v * v for v in values.values())) or 1
        return {t: v / norm for t, v in values.items()}

    q = vector(Counter(tokens(query)))
    scores = [sum(q.get(t, 0) * v for t, v in vector(count).items()) for count in counts]
    exact = [bool(codes(query) & codes(x)) for x in documents]
    order = sorted(range(n), key=lambda i: (-int(exact[i]), -scores[i], i))
    return [(i, scores[i], exact[i]) for i in order if scores[i] > 0 or exact[i]][:30]
