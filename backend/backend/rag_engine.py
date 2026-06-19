"""
RAG Engine — Semantic search over the laptop dataset using sentence embeddings.
Falls back to keyword search if sentence-transformers is not installed.
"""
import numpy as np
import pandas as pd

# ── Try to load sentence-transformers (optional but preferred) ────────────────
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Using keyword fallback.")


def _row_to_text(row: pd.Series) -> str:
    """Convert a dataset row into a natural-language sentence for embedding."""
    gpu = str(row.get("GPU", "")).strip()
    gpu_part = f"with {gpu} GPU" if gpu and gpu.lower() not in ("nan", "", "none") else "with integrated graphics"
    return (
        f"{row.get('Brand','')} {row.get('Laptop','')} — "
        f"{row.get('CPU','')} processor, "
        f"{row.get('RAM','')}GB RAM, "
        f"{row.get('Storage','')}GB storage, "
        f"{gpu_part}, "
        f"{row.get('Screen','')} inch screen, "
        f"priced at LKR {row.get('Price_LKR','')}"
    )


class RAGEngine:
    """
    Semantic retrieval engine.
    On first use it builds an in-memory embedding index for the laptop dataset.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.texts = [_row_to_text(row) for _, row in df.iterrows()]
        self._embeddings = None
        self._model = None

        if _ST_AVAILABLE:
            try:
                print("🔍 Loading embedding model (all-MiniLM-L6-v2)…")
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._embeddings = self._model.encode(
                    self.texts, show_progress_bar=False, convert_to_numpy=True
                )
                # L2-normalise so cosine similarity = dot product
                norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
                self._embeddings = self._embeddings / np.maximum(norms, 1e-9)
                print(f"✅ RAG index built: {len(self.texts)} laptops embedded.")
            except Exception as e:
                print(f"⚠️  Embedding model failed ({e}). Using keyword fallback.")
                self._model = None
                self._embeddings = None

    # ── Public API ────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 6) -> pd.DataFrame:
        """
        Return the top_k most relevant laptops for the given query.
        Uses semantic search if available, otherwise keyword overlap.
        """
        if self._model is not None and self._embeddings is not None:
            return self._semantic_search(query, top_k)
        return self._keyword_search(query, top_k)

    def get_context_for_prompt(self, query: str, top_k: int = 5) -> str:
        """Return a formatted string of top_k laptops ready to inject into an LLM prompt."""
        results = self.search(query, top_k)
        if results.empty:
            return "No matching laptops found in the dataset."
        lines = []
        for _, row in results.iterrows():
            lines.append(
                f"• {row.get('Brand','')} {row.get('Laptop','')} | "
                f"CPU: {row.get('CPU','')} | "
                f"RAM: {row.get('RAM','')}GB | "
                f"Storage: {row.get('Storage','')}GB | "
                f"GPU: {row.get('GPU','')} | "
                f"Screen: {row.get('Screen','')}\" | "
                f"Price: LKR {row.get('Price_LKR','')}"
            )
        return "\n".join(lines)

    # ── Internal methods ──────────────────────────────────────────────────────

    def _semantic_search(self, query: str, top_k: int) -> pd.DataFrame:
        q_vec = self._model.encode([query], convert_to_numpy=True)
        q_vec = q_vec / np.maximum(np.linalg.norm(q_vec), 1e-9)
        scores = (self._embeddings @ q_vec.T).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        return self.df.iloc[top_idx].copy()

    def _keyword_search(self, query: str, top_k: int) -> pd.DataFrame:
        tokens = set(query.lower().split())
        scored = []
        for i, text in enumerate(self.texts):
            text_tokens = set(text.lower().split())
            score = len(tokens & text_tokens)
            scored.append((score, i))
        scored.sort(reverse=True)
        top_idx = [i for _, i in scored[:top_k]]
        return self.df.iloc[top_idx].copy()
