"""Section-level search over manuals: exact identifiers, BM25 and vectors, fused by RRF.

Pure functions, no database. A document is split at its Markdown headings; every chunk
keeps its heading path so a hit can be traced back to "## 6 > ### 6.3". Question IDs are
deliberately not identifiers here: manuals may contain a question-to-section table, and
matching on IDs would read the answer from that table instead of from the content.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from app.retrieval.sparse import DTC, tokens

HEADING = re.compile(r"^(#{2,3}) +(.+?)\s*$", re.MULTILINE)
# Part, connector and tool codes as written in manuals: G31, GX9, N75, J623, V.A.G 1687, VAS 6150.
PART_CODE = re.compile(r"(?<![A-Za-z0-9.\-])([A-Z]{1,3}[0-9]{1,4}[A-Z]?)(?![A-Za-z0-9\-])")
# No \b: Chinese characters count as word characters, so "具备V.A.G 1687" would be missed.
TOOL_CODE = re.compile(r"(?<![A-Za-z0-9])(V\.?\s?A\.?\s?G|VAS)\s*([0-9]{3,5})(?![0-9])", re.I)
RRF_K = 60


@dataclass
class Chunk:
    document_id: str
    section: str            # "## 6. 接头座合…"
    subsection: str | None  # "### 6.3 A 类连接…" or None for the section's own lead text
    text: str
    start: int
    end: int
    identifiers: set = field(default_factory=set)

    @property
    def path(self):
        return " > ".join(h.lstrip("# ") for h in (self.section, self.subsection) if h)

    @property
    def search_text(self):
        return f"{self.path}\n{self.text}"


def identifiers(text):
    """Codes that must match exactly: fault codes, part/connector codes and tool numbers."""
    found = {code.upper() for code in DTC.findall(text)}
    found |= {m.group(1) for m in PART_CODE.finditer(text)}
    for m in TOOL_CODE.finditer(text):
        family = re.sub(r"[.\s]", "", m.group(1)).upper()
        found.add(family + m.group(2))
    return found


def split(document_id, body, skip_sections=()):
    """Chunks at ### level; a ## section's text before its first ### is its own chunk.

    Text before the first ## (title, front matter) is not searchable. Sections whose
    heading matches any pattern in skip_sections are left out entirely.
    """
    marks = [(m.start(), len(m.group(1)), m.group(0).strip()) for m in HEADING.finditer(body)]
    result = []
    section = None
    for index, (start, level, heading) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(body)
        if level == 2:
            section = heading
        if section is None or any(re.search(p, section) for p in skip_sections):
            continue
        text = body[start:end].strip()
        lines = text.splitlines()
        if len("\n".join(lines[1:]).strip()) == 0:
            continue  # heading only, e.g. a ## directly followed by its first ###
        result.append(Chunk(document_id, section, heading if level == 3 else None,
                            text, start, end, identifiers(text)))
    return result


# ---------------------------------------------------------------- channels

def exact_rank(query, chunks):
    """Chunks sharing at least one identifier with the query, most shared first."""
    wanted = identifiers(query)
    if not wanted:
        return []
    scored = [(len(wanted & c.identifiers), i) for i, c in enumerate(chunks)]
    return [i for score, i in sorted(scored, key=lambda x: (-x[0], x[1])) if score > 0]


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.counts = [Counter(tokens(t)) for t in texts]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / len(self.lengths) if self.lengths else 0
        df = Counter(term for count in self.counts for term in count)
        n = len(texts)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query):
        terms = Counter(tokens(query))
        result = []
        for count, length in zip(self.counts, self.lengths):
            norm = self.k1 * (1 - self.b + self.b * length / (self.average or 1))
            result.append(sum(self.idf.get(t, 0) * count[t] * (self.k1 + 1) / (count[t] + norm)
                              for t in terms if t in count))
        return result

    def rank(self, query):
        scores = self.scores(query)
        return [i for i in sorted(range(len(scores)), key=lambda i: (-scores[i], i)) if scores[i] > 0]


def dense_rank(query_vector, chunk_vectors):
    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1
        nb = math.sqrt(sum(y * y for y in b)) or 1
        return dot / (na * nb)
    scores = [cosine(query_vector, v) for v in chunk_vectors]
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


def rrf(rankings, k=RRF_K):
    """Reciprocal rank fusion: each list adds 1/(k + position) to the items it ranks."""
    total = Counter()
    for ranking in rankings:
        for position, item in enumerate(ranking, 1):
            total[item] += 1 / (k + position)
    return [item for item, _ in sorted(total.items(), key=lambda x: (-x[1], x[0]))]
