"""Choose which manual sections an analysis sends, by searching the manual's own text.

No question-to-section table: each saved record is searched as "question title: chosen
options", each unanswered question by its title, inside the area's own document. Whole
`##` sections are sent verbatim; a document's always-included sections (set per document
in the reference manifest) are added. Free-text notes do not take part in the search.
"""
import hashlib
import json
import re
from pathlib import Path

from app.retrieval.section_search import BM25, dense_rank, exact_rank, rrf, split

METHOD_VERSION = "retrieval-reading-v1"
QUESTION_ID = re.compile(r"^[A-Z]{1,4}-[0-9]{2}\s*·\s*")
# Navigation parts of a manual (reading entry, question/ID tables, notes for the AI, sources)
# are not evidence for a record; searching them would match on question wording alone.
NAVIGATION = ("阅读入口", "快速入口", "对应关系", "问题与.*选项", "问题、选项",
              "提供给 AI", "一起用于分析", r"^## [0-9]+\. *(资料)?来源")
HEADING2 = re.compile(r"^## .+$", re.MULTILINE)


def plain_title(title):
    return QUESTION_ID.sub("", title).strip()


def section_ranges(body):
    """Each `##` heading -> (start, end) of the whole section, ending at the next `##`."""
    marks = [(m.start(), m.group(0).strip()) for m in HEADING2.finditer(body)]
    return {heading: (start, marks[i + 1][0] if i + 1 < len(marks) else len(body))
            for i, (start, heading) in enumerate(marks)}


def queries_for(payload):
    """Search text for every record and unanswered question in the payload."""
    titles = {q["id"]: plain_title(q.get("title", q["id"])) for q in payload.get("questions", [])}
    result = []
    for record in payload["observations"]:
        labels = "、".join(record.get("option_labels") or [])
        title = titles.get(record["question_id"]) or plain_title(record.get("question", ""))
        result.append({"text": f"{title}：{labels}" if labels else title, "reason": "recorded_question",
                       "question_id": record["question_id"], "observation_id": str(record["id"]),
                       "option_ids": list(record.get("option_ids", []))})
    for question_id in payload.get("unknown_question_ids", []):
        if titles.get(question_id):
            result.append({"text": titles[question_id], "reason": "unknown_fact_method",
                           "question_id": question_id})
    return result


class Embeddings:
    """Chunk vectors cached by content (memory and optional disk); query vectors memoised.

    model may be a zero-argument callable returning the model, so loading is deferred to
    the first search and a missing model only affects that search.
    """

    def __init__(self, model, cache_dir=None, fingerprint=None):
        self._model, self.cache_dir = model, Path(cache_dir) if cache_dir else None
        self.fingerprint = fingerprint
        self.memory, self.queries = {}, {}

    def warm(self):
        """Load the model now (outside any lock). A failure is left for the search to report."""
        try:
            self.model
        except Exception:
            pass

    @property
    def model(self):
        if callable(self._model) and not hasattr(self._model, "embed_query"):
            self._model = self._model()
        return self._model

    def documents(self, texts):
        keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if k not in self.memory]
        if missing and self.cache_dir:
            for k, _ in missing:
                path = self.cache_dir / f"{k}.json"
                if path.is_file():
                    self.memory[k] = json.loads(path.read_text(encoding="utf-8"))
            missing = [(k, t) for k, t in missing if k not in self.memory]
        if missing:
            vectors = self.model.embed_documents([t for _, t in missing])
            for (k, _), vector in zip(missing, vectors):
                self.memory[k] = [float(x) for x in vector]
                if self.cache_dir:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    (self.cache_dir / f"{k}.json").write_text(json.dumps(self.memory[k]), encoding="utf-8")
        return [self.memory[k] for k in keys]

    def query(self, text):
        if text not in self.queries:
            self.queries[text] = [float(x) for x in self.model.embed_query(text)]
        return self.queries[text]


ROUTE_DEPTH = 10   # chunks per text that vote for their document
ROUTE_KEEP = 0.6   # documents scoring at least this share of the best one are read too


def route_documents(texts, rank, chunks, *, depth=ROUTE_DEPTH, keep=ROUTE_KEEP):
    """Step one of two-step retrieval: which documents an area should read.

    Each text describing the area (its title and description, each question title) ranks the
    chunks of every candidate document; its top `depth` chunks vote 1/(60+position) for their
    document. Returns [(document_id, score)] best first, cut to the documents scoring at least
    `keep` times the best. No table says which manual belongs to which area.
    """
    votes = {}
    for text in texts:
        for position, index in enumerate(rank(text)[:depth], 1):
            document = chunks[index].document_id
            votes[document] = votes.get(document, 0.0) + 1 / (60 + position)
    if not votes:
        return []
    best = max(votes.values())
    ordered = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    return [(document, round(score, 4)) for document, score in ordered if score >= keep * best]


def area_texts(area, questions):
    """What describes an area for choosing its manuals: title and description, each question title."""
    texts = [f"{area['title']}：{area.get('description') or ''}"]
    return texts + [plain_title(q["title"]) for q in questions if q.get("area_id") == area["id"]]


def computed_pool(document, embeddings=None):
    """Searchable chunks of a document split now, with vectors when a model is given."""
    pieces = split(document["id"], document["body"], NAVIGATION)
    return pieces, (embeddings.documents([c.search_text for c in pieces]) if embeddings is not None else None)


def choose_documents(documents, texts, *, embeddings=None, pool=None):
    """Step one for an area: which of the candidate manuals to read, best first, with scores.

    pool(document) -> (chunks, vectors or None) supplies stored data; without it (or when it
    returns None) the document is split and embedded now.
    """
    chunks, vectors = [], []
    for document in documents:
        stored = pool(document) if pool is not None else None
        pieces, piece_vectors = stored if stored is not None else computed_pool(document, embeddings)
        chunks.extend(pieces)
        vectors = None if vectors is None or piece_vectors is None else vectors + list(piece_vectors)
    if not chunks:
        return []
    index = BM25([c.search_text for c in chunks])

    def rank(text):
        rankings = [exact_rank(text, chunks), index.rank(text)]
        if embeddings is not None and vectors is not None:
            rankings.append(dense_rank(embeddings.query(text), vectors))
        return rrf(rankings)
    return route_documents(texts, rank, chunks)


class ComputedSections:
    """Search one document by splitting its body now; vectors from the model (disk-cached).

    Used when a document has no stored chunks for the current model, and by offline
    evaluations that run without a database.
    """
    source = "computed"

    def __init__(self, document, embeddings=None):
        self.chunks = split(document["id"], document["body"], NAVIGATION)
        self.index = BM25([c.search_text for c in self.chunks]) if self.chunks else None
        self.embeddings = embeddings
        self.vectors = (embeddings.documents([c.search_text for c in self.chunks])
                        if embeddings is not None and self.chunks else None)

    def exact(self, query):
        return exact_rank(query, self.chunks)

    def keywords(self, query):
        return self.index.rank(query)

    def dense(self, query):
        if self.embeddings is None:
            return None
        return dense_rank(self.embeddings.query(query), self.vectors)


def rank_sections(query, source):
    """Whole `##` sections, best first, fusing exact codes, BM25 and vectors (RRF)."""
    rankings = [source.exact(query), source.keywords(query)]
    dense = source.dense(query)
    if dense is not None:
        rankings.append(dense)
    order = []
    for i in rrf(rankings):
        if source.chunks[i].section not in order:
            order.append(source.chunks[i].section)
    return order


def select_sections(document, queries, *, top_k, always_include=(), embeddings=None, source=None):
    """Sections to send for one document, each with why it was chosen.

    source is where chunks, keyword index and vectors come from (stored in the database or
    computed now); both give the same chunks, so the same sections. Returns None when the
    document has no searchable `##` structure; the caller then keeps the full body.
    """
    body = document["body"]
    ranges = section_ranges(body)
    source = source if source is not None else ComputedSections(document, embeddings)
    if not ranges or not source.chunks:
        return None
    selected = {}
    for heading in always_include:
        if heading not in ranges:
            raise ValueError(f"Always-included section not found in {document['id']}: {heading}")
        selected[heading] = {"reason": "context_conditions_and_verification", "question_ids": [], "selected_by": []}
    for query in queries:
        for heading in rank_sections(query["text"], source)[:top_k]:
            entry = selected.setdefault(heading, {"reason": query["reason"], "question_ids": [], "selected_by": []})
            if query["question_id"] not in entry["question_ids"]:
                entry["question_ids"].append(query["question_id"])
            if query.get("observation_id"):
                entry["selected_by"].append({"observation_id": query["observation_id"],
                                             "option_ids": query["option_ids"]})
    return [{"heading": heading, "start": ranges[heading][0], "end": ranges[heading][1], **why}
            for heading, why in sorted(selected.items(), key=lambda item: ranges[item[0]][0])]
