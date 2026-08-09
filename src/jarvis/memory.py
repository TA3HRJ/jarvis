"""Gömülü hafıza katmanı: SQLite + sqlite-vec. Ayrı bir sunucu süreci yok
(CLAUDE.md bağlayıcı kural: "Gömülü hafıza katmanı, sunucu değil")."""

import sqlite3
import time

import sqlite_vec

DB_PATH = "jarvis_memory.db"
EMBED_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 ile aynı model, Katman 2 ile paylaşılıyor

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer

        _embed_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu"
        )
    return _embed_model


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
            memory_id INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBED_DIM}]
        )
    """)
    return conn


def remember(text: str, db_path: str = DB_PATH) -> int:
    """Bir bilgiyi kalıcı hafızaya yazar, embedding'ini çıkarır ve indeksler."""
    model = _get_embed_model()
    embedding = model.encode([text], normalize_embeddings=True)[0]
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO memories (text, created_at) VALUES (?, ?)", (text, time.time())
        )
        memory_id = cur.lastrowid
        conn.execute(
            "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
            (memory_id, sqlite_vec.serialize_float32(embedding.tolist())),
        )
        conn.commit()
        return memory_id
    finally:
        conn.close()


def recall(query: str, k: int = 5, db_path: str = DB_PATH) -> list[dict]:
    """Sorguya semantik olarak en yakın k hafızayı döndürür."""
    model = _get_embed_model()
    query_embedding = model.encode([query], normalize_embeddings=True)[0]
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT m.id, m.text, m.created_at, v.distance
            FROM memory_vectors v
            JOIN memories m ON m.id = v.memory_id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(query_embedding.tolist()), k),
        ).fetchall()
        return [
            {"id": r[0], "text": r[1], "created_at": r[2], "distance": r[3]} for r in rows
        ]
    finally:
        conn.close()
