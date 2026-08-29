# -*- coding: utf-8 -*-
"""
RAG 检索增强引擎：文档加载、切分、向量化、FAISS 存储、相似度检索
支持两种 embedding 模式：
  1. sentence-transformers（需安装，效果好）
  2. fallback 哈希向量化（纯 numpy，零额外依赖，开箱即用）
向量存储：
  1. faiss-cpu（需安装，速度快）
  2. numpy 暴力检索（零依赖 fallback）
"""
import os
import re
import pickle
import numpy as np
from config import RAG_CONFIG


class RAGEngine:
    def __init__(self, knowledge_dir: str = None, index_path: str = None):
        self.knowledge_dir = knowledge_dir or RAG_CONFIG["knowledge_dir"]
        self.index_path = index_path or RAG_CONFIG["index_path"]
        self.chunk_size = RAG_CONFIG["chunk_size"]
        self.chunk_overlap = RAG_CONFIG["chunk_overlap"]
        self.top_k = RAG_CONFIG["top_k"]

        self.chunks = []          # 文本块列表
        self.chunk_sources = []   # 每个块的来源文件名
        self.embeddings = None    # 向量矩阵 (n, dim)
        self.index = None         # faiss 索引或 None

        # 检测可用的 embedding 后端
        self._embedding_backend = self._detect_embedding_backend()
        self._vector_backend = self._detect_vector_backend()
        self._embedder = None  # sentence-transformers 模型实例

    # ========== 后端检测 ==========
    def _detect_embedding_backend(self) -> str:
        try:
            from sentence_transformers import SentenceTransformer
            return "sentence_transformers"
        except ImportError:
            return "fallback"

    def _detect_vector_backend(self) -> str:
        try:
            import faiss
            return "faiss"
        except ImportError:
            return "numpy"

    def backend_info(self) -> dict:
        return {
            "embedding": self._embedding_backend,
            "vector_store": self._vector_backend,
            "chunk_count": len(self.chunks),
        }

    # ========== 文档加载 ==========
    def load_documents(self, knowledge_dir: str = None) -> int:
        """加载知识库目录下所有 .txt / .md / .csv 文件，返回加载的文档数"""
        kdir = knowledge_dir or self.knowledge_dir
        if not os.path.exists(kdir):
            os.makedirs(kdir, exist_ok=True)
            return 0

        self.chunks = []
        self.chunk_sources = []

        doc_count = 0
        for filename in sorted(os.listdir(kdir)):
            filepath = os.path.join(kdir, filename)
            if not os.path.isfile(filepath):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".txt", ".md", ".csv"):
                continue

            text = self._read_file(filepath)
            if not text.strip():
                continue

            chunks = self._split_text(text)
            for chunk in chunks:
                self.chunks.append(chunk)
                self.chunk_sources.append(filename)
            doc_count += 1

        return doc_count

    def _read_file(self, filepath: str) -> str:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            import pandas as pd
            df = pd.read_csv(filepath)
            return df.to_string(index=False)
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    # ========== 文本切分 ==========
    def _split_text(self, text: str) -> list:
        """按固定大小滑动窗口切分，保留重叠"""
        text = re.sub(r"\n{3,}", "\n\n", text.strip())
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - self.chunk_overlap
        return chunks

    # ========== 向量化 ==========
    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        if self._embedding_backend == "sentence_transformers":
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(RAG_CONFIG["embedding_model"])
        return self._embedder

    def _embed(self, texts: list) -> np.ndarray:
        """将文本列表转为向量矩阵"""
        if self._embedding_backend == "sentence_transformers":
            model = self._get_embedder()
            vectors = model.encode(texts, normalize_embeddings=True)
            return np.array(vectors, dtype=np.float32)
        else:
            return self._hash_embed(texts)

    def _hash_embed(self, texts: list) -> np.ndarray:
        """
        fallback：基于字符 n-gram 的哈希向量化（纯 numpy）
        对中文文本做字级 2-gram + 3-gram 特征哈希
        """
        dim = RAG_CONFIG["fallback_dim"]
        vectors = np.zeros((len(texts), dim), dtype=np.float32)
        for i, text in enumerate(texts):
            # 字级 n-gram
            chars = list(text.replace(" ", "").replace("\n", ""))
            grams = set()
            for n in (2, 3):
                for j in range(len(chars) - n + 1):
                    grams.add("".join(chars[j:j + n]))
            # 关键词加权
            for gram in grams:
                h = hash(gram) % dim
                vectors[i][h] += 1.0
            # 归一化
            norm = np.linalg.norm(vectors[i])
            if norm > 0:
                vectors[i] /= norm
        return vectors

    # ========== 构建索引 ==========
    def build_index(self):
        """对已加载的文本块构建向量索引"""
        if not self.chunks:
            raise ValueError("没有可索引的文档，请先调用 load_documents()")

        self.embeddings = self._embed(self.chunks)

        if self._vector_backend == "faiss":
            import faiss
            dim = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)  # 内积（已归一化=余弦相似度）
            self.index.add(self.embeddings)
        else:
            self.index = None  # numpy 模式直接用矩阵

        return len(self.chunks)

    # ========== 检索 ==========
    def retrieve(self, query: str, top_k: int = None, min_score: float = 0.3) -> list:
        """
        根据查询文本检索最相关的 top_k 个文本块
        返回 [{"text": ..., "source": ..., "score": ...}, ...]
        min_score: 相关性阈值，低于此值的结果被过滤
        """
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        k = top_k or self.top_k
        k = min(k, len(self.chunks))

        query_vec = self._embed([query])

        if self._vector_backend == "faiss" and self.index is not None:
            scores, indices = self.index.search(query_vec, k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                # FAISS内积分数值通常>0，归一化后与余弦相似度可比
                normalized_score = float(score)
                if normalized_score < min_score:
                    continue
                results.append({
                    "text": self.chunks[idx],
                    "source": self.chunk_sources[idx],
                    "score": round(normalized_score, 4),
                })
            return results
        else:
            # numpy 暴力余弦相似度
            similarities = np.dot(self.embeddings, query_vec[0])
            top_indices = np.argsort(similarities)[::-1][:k]
            results = []
            for idx in top_indices:
                sim = float(similarities[idx])
                if sim < min_score:
                    continue
                results.append({
                    "text": self.chunks[idx],
                    "source": self.chunk_sources[idx],
                    "score": round(sim, 4),
                })
            return results

    def retrieve_as_context(self, query: str, top_k: int = None) -> str:
        """检索并格式化为 LLM prompt 可用的上下文字符串"""
        results = self.retrieve(query, top_k)
        if not results:
            return ""
        lines = ["以下是从知识库中检索到的相关参考资料："]
        for i, r in enumerate(results, 1):
            lines.append(f"\n--- 参考资料 {i}（来源：{r['source']}，相关度：{r['score']}）---")
            lines.append(r["text"])
        return "\n".join(lines)

    # ========== 索引保存/加载 ==========
    def save_index(self):
        """保存索引到磁盘"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        data = {
            "chunks": self.chunks,
            "chunk_sources": self.chunk_sources,
            "embeddings": self.embeddings,
            "embedding_backend": self._embedding_backend,
            "vector_backend": self._vector_backend,
        }
        with open(self.index_path + ".pkl", "wb") as f:
            pickle.dump(data, f)
        # faiss 索引单独保存
        if self._vector_backend == "faiss" and self.index is not None:
            import faiss
            faiss.write_index(self.index, self.index_path + ".faiss")

    def load_index(self) -> bool:
        """从磁盘加载索引，成功返回 True"""
        pkl_path = self.index_path + ".pkl"
        if not os.path.exists(pkl_path):
            return False
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        self.chunks = data["chunks"]
        self.chunk_sources = data["chunk_sources"]
        self.embeddings = data["embeddings"]
        if self._vector_backend == "faiss":
            faiss_path = self.index_path + ".faiss"
            if os.path.exists(faiss_path):
                import faiss
                self.index = faiss.read_index(faiss_path)
        return True

    # ========== 一键初始化 ==========
    def initialize(self, force_rebuild: bool = False) -> dict:
        """
        初始化 RAG 引擎：优先加载已有索引，否则从知识库构建
        返回状态信息
        """
        if not force_rebuild and self.load_index():
            return {
                "status": "loaded",
                "message": f"已加载缓存索引，共 {len(self.chunks)} 个文本块",
                "backend": self.backend_info(),
            }

        doc_count = self.load_documents()
        if doc_count == 0:
            return {
                "status": "empty",
                "message": "知识库目录为空，请在 data/knowledge/ 下放入 .txt/.md/.csv 文件",
                "backend": self.backend_info(),
            }

        chunk_count = self.build_index()
        self.save_index()
        return {
            "status": "built",
            "message": f"已从 {doc_count} 个文档构建索引，共 {chunk_count} 个文本块",
            "backend": self.backend_info(),
        }
