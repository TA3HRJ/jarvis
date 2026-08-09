"""3 katmanlı niyet yönlendirici: Katman 1 (regex) -> Katman 2 (embedding) -> Katman 3 (yerel LLM)."""

from dataclasses import dataclass

import numpy as np

from .catalog import CATALOG, Intent

LAYER2_THRESHOLD = 0.72
LAYER3_MIN_SIMILARITY = 0.35  # bunun altındaysa soru kataloğa hiç yakın değil, Katman 3'ü boşuna denemeye değmez


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


def _layer2_best(text: str) -> tuple[Intent, float]:
    model = _get_embed_model()
    catalog_emb = _get_catalog_embeddings()
    query_emb = model.encode([text], normalize_embeddings=True)[0]
    sims = catalog_emb @ query_emb
    best_i = int(np.argmax(sims))
    return _catalog_index[best_i][0], float(sims[best_i])


def layer2_match(text: str) -> RouteResult | None:
    intent, best_score = _layer2_best(text)
    if best_score < LAYER2_THRESHOLD:
        return None
    slots = intent.match_regex(text) or {}
    if intent.slots and not slots:
        return None  # niyet bulundu ama slot dolduramadık, katman 3'e bırak
    return RouteResult(intent=intent.name, slots=slots, layer=2, confidence=best_score)


def warm_up() -> None:
    """Embedding modelini ve katalog vektörlerini önceden yükler — ilk gerçek sorguda
    ~13sn'lik soğuk başlangıç gecikmesi olmasın diye servis açılışında çağrılır."""
    _get_catalog_embeddings()


def route(text: str, use_layer3: bool = True) -> RouteResult:
    result = layer1_match(text)
    if result is not None:
        return result

    intent, best_score = _layer2_best(text)
    if best_score >= LAYER2_THRESHOLD:
        slots = intent.match_regex(text) or {}
        if not (intent.slots and not slots):
            return RouteResult(intent=intent.name, slots=slots, layer=2, confidence=best_score)

    # Skor kataloğa hiç yakın değilse Katman 3'ü (yerel LLM, GPU'ya yükleme maliyeti var)
    # boşuna denemeye değmez — canlı testte açık uçlu sorularda gereksiz ~2-3sn ekliyordu.
    if use_layer3 and best_score >= LAYER3_MIN_SIMILARITY:
        from .layer3 import layer3_match

        result = layer3_match(text)
        if result is not None:
            return result
    return RouteResult(intent=None, slots={}, layer=0, confidence=0.0)
