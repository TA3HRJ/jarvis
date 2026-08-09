"""3 katmanlı niyet yönlendirici: Katman 1 (regex) -> Katman 2 (embedding) -> Katman 3 (yerel LLM)."""

from dataclasses import dataclass

import numpy as np

from .catalog import CATALOG, Intent

LAYER2_THRESHOLD = 0.72


@dataclass
class RouteResult:
    intent: str | None
    slots: dict
    layer: int  # 1, 2, 3 ya da 0 (eşleşme yok)
    confidence: float = 1.0


def layer1_match(text: str) -> RouteResult | None:
    for intent in CATALOG:
        slots = intent.match_regex(text)
        if slots is not None:
            return RouteResult(intent=intent.name, slots=slots, layer=1, confidence=1.0)
    return None


_embed_model = None
_catalog_embeddings = None
_catalog_index: list[tuple[Intent, str]] = []


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer

        _embed_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu"
        )
    return _embed_model


def _get_catalog_embeddings():
    global _catalog_embeddings, _catalog_index
    if _catalog_embeddings is None:
        model = _get_embed_model()
        _catalog_index = [(intent, phrase) for intent in CATALOG for phrase in intent.example_phrases]
        phrases = [p for _, p in _catalog_index]
        _catalog_embeddings = model.encode(phrases, normalize_embeddings=True)
    return _catalog_embeddings


def layer2_match(text: str) -> RouteResult | None:
    model = _get_embed_model()
    catalog_emb = _get_catalog_embeddings()
    query_emb = model.encode([text], normalize_embeddings=True)[0]
    sims = catalog_emb @ query_emb
    best_i = int(np.argmax(sims))
    best_score = float(sims[best_i])
    if best_score < LAYER2_THRESHOLD:
        return None
    intent, _ = _catalog_index[best_i]
    slots = intent.match_regex(text) or {}
    if intent.slots and not slots:
        return None  # niyet bulundu ama slot dolduramadık, katman 3'e bırak
    return RouteResult(intent=intent.name, slots=slots, layer=2, confidence=best_score)


def route(text: str, use_layer3: bool = True) -> RouteResult:
    for fn in (layer1_match, layer2_match):
        result = fn(text)
        if result is not None:
            return result
    if use_layer3:
        from .layer3 import layer3_match

        result = layer3_match(text)
        if result is not None:
            return result
    return RouteResult(intent=None, slots={}, layer=0, confidence=0.0)
