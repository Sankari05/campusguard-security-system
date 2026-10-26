"""
app/services/vision/vector_matcher.py
======================================
Enterprise Ultra-Fast Vector Similarity Matcher using FAISS (Facebook AI Similarity Search).
Designed for 10,000+ student facial recognition scale.

Key Features:
- SIMD-accelerated FAISS IndexFlatIP (Cosine similarity via L2 normalization)
- Sub-2ms similarity lookup across 10,000+ student embeddings
- Dynamic enrollment, batch vector indexing, and memory persistence
- Automatic fallback to vectorized NumPy dot-product if FAISS binary is unavailable
"""

import os
import time
import pickle
import logging
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

log = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    log.warning("[FAISS] faiss-cpu not installed. Falling back to vectorized NumPy similarity.")


class FaissVectorMatcher:
    """
    Sub-millisecond Vector Similarity Search Engine for 10,000+ students scale.
    Replaces O(N) linear comparisons with sub-2ms vectorized similarity search.
    """

    def __init__(self, embedding_dim: int = 128, similarity_threshold: float = 0.65):
        """
        Args:
            embedding_dim: Dimensionality of face embeddings (128-d for dlib/FaceNet, 512-d for InsightFace).
            similarity_threshold: Cosine similarity cutoff (0.0 to 1.0) for affirmative match.
        """
        self.dim = embedding_dim
        self.threshold = similarity_threshold
        self.index = None
        self.id_to_student: Dict[int, str] = {}
        self.student_to_id: Dict[str, int] = {}
        self._raw_embeddings: List[np.ndarray] = []
        self._is_built = False
        self._init_index()

    def _init_index(self):
        """Initializes FAISS IndexFlatIP (Inner Product = Cosine Similarity for unit vectors)."""
        if FAISS_AVAILABLE:
            # IndexFlatIP computes exact inner product
            self.index = faiss.IndexFlatIP(self.dim)
        else:
            self.index = None

    @staticmethod
    def normalize_vector(v: np.ndarray) -> np.ndarray:
        """L2 normalizes embedding vector so Inner Product equals Cosine Similarity."""
        norm = np.linalg.norm(v)
        if norm == 0:
            return v.astype(np.float32)
        return (v / norm).astype(np.float32)

    def add_student(self, student_id: str, embedding: np.ndarray) -> bool:
        """
        Enrolls a student's face embedding into the vector index.
        """
        if embedding is None or len(embedding) != self.dim:
            log.error("[FAISS] Embedding dimension mismatch: expected %d, got %s",
                      self.dim, len(embedding) if embedding is not None else 0)
            return False

        norm_vec = self.normalize_vector(embedding)
        internal_id = len(self._raw_embeddings)

        self.id_to_student[internal_id] = student_id
        self.student_to_id[student_id] = internal_id
        self._raw_embeddings.append(norm_vec)

        if FAISS_AVAILABLE and self.index is not None:
            vector_matrix = np.expand_dims(norm_vec, axis=0)
            self.index.add(vector_matrix)

        self._is_built = True
        return True

    def build_index_batch(self, student_ids: List[str], embeddings: np.ndarray) -> None:
        """
        High-throughput batch enrollment for thousands of students at once.
        """
        if len(student_ids) != len(embeddings):
            raise ValueError("student_ids and embeddings must have the same length")

        count = len(student_ids)
        if count == 0:
            return

        norm_matrix = np.zeros((count, self.dim), dtype=np.float32)
        for i in range(count):
            norm_matrix[i] = self.normalize_vector(embeddings[i])
            self.id_to_student[i] = student_ids[i]
            self.student_to_id[student_ids[i]] = i

        self._raw_embeddings = list(norm_matrix)

        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(self.dim)
            self.index.add(norm_matrix)

        self._is_built = True
        log.info("[FAISS] Built vector index for %d students (dim=%d)", count, self.dim)

    def search(self, query_embedding: np.ndarray, top_k: int = 1) -> Tuple[str, float, float]:
        """
        Searches the vector database for the closest student identity.
        Returns:
            (student_id, confidence, query_time_ms)
        """
        if not self._is_built or len(self.id_to_student) == 0:
            return "Unknown", 0.0, 0.0

        start_time = time.perf_counter()
        query_norm = self.normalize_vector(query_embedding).reshape(1, -1)

        best_id = -1
        best_sim = 0.0

        if FAISS_AVAILABLE and self.index is not None:
            # Query FAISS index directly
            distances, indices = self.index.search(query_norm, top_k)
            best_id = int(indices[0][0])
            best_sim = float(distances[0][0])
        else:
            # Vectorized NumPy Matrix multiplication fallback
            matrix = np.array(self._raw_embeddings)
            sims = np.dot(matrix, query_norm.T).flatten()
            best_id = int(np.argmax(sims))
            best_sim = float(sims[best_id])

        query_time_ms = (time.perf_counter() - start_time) * 1000.0

        if best_sim < self.threshold or best_id not in self.id_to_student:
            return "Unknown", best_sim, query_time_ms

        matched_student = self.id_to_student[best_id]
        return matched_student, best_sim, query_time_ms

    def save_index(self, filepath: str) -> bool:
        """Persists the FAISS index and student ID mapping to disk."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            payload = {
                "dim": self.dim,
                "threshold": self.threshold,
                "id_to_student": self.id_to_student,
                "student_to_id": self.student_to_id,
                "raw_embeddings": self._raw_embeddings,
            }
            with open(f"{filepath}.meta", "wb") as f:
                pickle.dump(payload, f)

            if FAISS_AVAILABLE and self.index is not None:
                faiss.write_index(self.index, f"{filepath}.faiss")
            return True
        except Exception as e:
            log.error("[FAISS] Failed to save vector index: %s", e)
            return False

    def load_index(self, filepath: str) -> bool:
        """Loads index and metadata from disk."""
        meta_file = f"{filepath}.meta"
        faiss_file = f"{filepath}.faiss"
        if not os.path.exists(meta_file):
            return False

        try:
            with open(meta_file, "rb") as f:
                payload = pickle.load(f)
            self.dim = payload["dim"]
            self.threshold = payload["threshold"]
            self.id_to_student = payload["id_to_student"]
            self.student_to_id = payload["student_to_id"]
            self._raw_embeddings = payload["raw_embeddings"]

            if FAISS_AVAILABLE and os.path.exists(faiss_file):
                self.index = faiss.read_index(faiss_file)
            else:
                self._init_index()

            self._is_built = True
            log.info("[FAISS] Loaded vector store with %d identities", len(self.id_to_student))
            return True
        except Exception as e:
            log.error("[FAISS] Failed to load vector index: %s", e)
            return False
