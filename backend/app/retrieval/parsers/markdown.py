from app.domain.documents import IngestError
from markdown_it import MarkdownIt

VERSION = "markdown-it-source-v1"


def decode(data):
    try:
        value = data.decode("utf-8-sig")
    except UnicodeError:
        raise IngestError("INVALID_MARKDOWN_ENCODING") from None
    if not value.strip() or "\x00" in value or value.lstrip().startswith("%PDF-"):
        raise IngestError("INVALID_MARKDOWN")
    return value


def parse(data, stopped):
    value = decode(data)
    lines = value.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(value)
    blocks, headings, context = [], [], None
    previous_end = 0
    for index, token in enumerate(tokens):
        if stopped.is_set():
            raise IngestError("PARSE_STOPPED")
        if token.level != 0 or not token.map or token.nesting == -1:
            continue
        first, last = token.map
        start, end = offsets[first], offsets[last]
        if start < previous_end:
            continue
        if token.type == "heading_open":
            level = int(token.tag[1:])
            headings = headings[: level - 1] + [tokens[index + 1].content]
            context = None
        kind = (
            "table"
            if token.type == "table_open"
            else "list"
            if token.type in {"bullet_list_open", "ordered_list_open"}
            else "paragraph"
        )
        # Include inter-block whitespace in source coverage, never fetch linked resources.
        source_start = previous_end
        block = dict(
            text=value[source_start:end],
            char_start=source_start,
            char_end=end,
            heading_path=list(headings),
            kind=kind,
            locator=dict(
                line_start=value.count("\n", 0, source_start) + 1,
                line_end=last,
                context=context,
                source="markdown-decoded-utf8",
            ),
        )
        if kind == "table":
            block["header"] = "".join(lines[first : min(first + 2, last)])
        blocks.append(block)
        if token.type == "paragraph_open" and context is None:
            context = dict(char_start=start, char_end=end, line_start=first + 1, line_end=last)
        previous_end = end
    if previous_end < len(value):
        blocks.append(
            dict(
                text=value[previous_end:],
                char_start=previous_end,
                char_end=len(value),
                heading_path=list(headings),
                kind="paragraph",
                locator={"source": "markdown-decoded-utf8"},
            )
        )
    return dict(blocks=blocks, page_count=None, page_issues=[], parser_version=VERSION)
