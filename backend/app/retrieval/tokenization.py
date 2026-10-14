import base64
import hashlib
from functools import lru_cache
from pathlib import Path

import tiktoken

NAME = "cl100k_base:223921b7:ordinary-v1"


@lru_cache(maxsize=1)
def encoding():
    raw = (Path(__file__).parent / "assets" / "cl100k_base.tiktoken").read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
    ):
        raise RuntimeError("Tokenizer asset integrity failure")
    ranks = {
        base64.b64decode(token): int(rank)
        for token, rank in (line.split() for line in raw.splitlines())
    }
    return tiktoken.Encoding(
        name="xiutu_cl100k_ordinary",
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s",
        mergeable_ranks=ranks,
        special_tokens={},
    )


def count(text):
    return len(encoding().encode_ordinary(text))
