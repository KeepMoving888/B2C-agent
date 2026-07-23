"""检索器测试

覆盖模块①③核心能力：
- CoT 查询扩展（变体生成）
- 结果去重（按 doc_id 保留高分）
- RRF 融合（两路检索结果合并）
- 分词（中英文混合）
"""
import pytest
from app.rag.retriever import _cot_expand_query, _dedup_results, _rrf_fusion, _tokenize


class TestCotExpandQuery:
    """CoT 查询扩展测试"""

    def test_original_always_preserved(self):
        variants = _cot_expand_query("蓝牙耳机续航")
        assert "蓝牙耳机续航" in variants
        assert len(variants) >= 1

    def test_question_word_removed(self):
        variants = _cot_expand_query("蓝牙耳机怎么充电")
        # 应生成去除"怎么"的变体
        assert len(variants) >= 2
        # 至少有一个变体不含"怎么"
        assert any("怎么" not in v for v in variants)

    def test_entity_extraction(self):
        variants = _cot_expand_query("智能手表的续航时间")
        # 应提取中文实体
        assert len(variants) >= 2

    def test_english_keywords(self):
        variants = _cot_expand_query("how long does the battery last")
        # 应提取英文关键词
        assert len(variants) >= 2

    def test_empty_query(self):
        variants = _cot_expand_query("")
        assert variants == [""]

    def test_dedup_variants(self):
        """重复变体应被去重"""
        variants = _cot_expand_query("earphone")
        assert len(variants) == len(set(variants))


class TestDedupResults:
    """结果去重测试"""

    def test_dedup_by_doc_id(self):
        results = [
            {"id": "doc1", "content": "a", "score": 0.9},
            {"id": "doc2", "content": "b", "score": 0.8},
            {"id": "doc1", "content": "a", "score": 0.95},  # 更高分的重复
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 2
        # doc1 应保留高分版本
        doc1 = [r for r in deduped if r["id"] == "doc1"][0]
        assert doc1["score"] == 0.95

    def test_empty_results(self):
        assert _dedup_results([]) == []

    def test_no_duplicates(self):
        results = [
            {"id": "doc1", "score": 0.9},
            {"id": "doc2", "score": 0.8},
        ]
        assert len(_dedup_results(results)) == 2

    def test_skip_empty_id(self):
        results = [
            {"id": "", "score": 0.9},
            {"id": "doc1", "score": 0.8},
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1


class TestRrfFusion:
    """RRF 融合测试"""

    def test_fuse_two_lists(self):
        vec = [
            {"id": "doc1", "content": "a", "score": 0.9, "source": "vector"},
            {"id": "doc2", "content": "b", "score": 0.8, "source": "vector"},
        ]
        bm25 = [
            {"id": "doc2", "content": "b", "score": 2.5, "source": "bm25"},
            {"id": "doc3", "content": "c", "score": 1.8, "source": "bm25"},
        ]
        fused = _rrf_fusion(vec, bm25)
        assert len(fused) == 3  # doc1, doc2, doc3
        # doc2 在两路中都出现，应排名靠前
        assert fused[0]["id"] == "doc2"

    def test_empty_inputs(self):
        assert _rrf_fusion([], []) == []

    def test_single_list(self):
        vec = [{"id": "doc1", "content": "a", "score": 0.9, "source": "vector"}]
        fused = _rrf_fusion(vec, [])
        assert len(fused) == 1

    def test_fused_score_positive(self):
        vec = [{"id": "doc1", "content": "a", "score": 0.9, "source": "vector"}]
        bm25 = [{"id": "doc1", "content": "a", "score": 2.0, "source": "bm25"}]
        fused = _rrf_fusion(vec, bm25)
        assert fused[0]["score"] > 0


class TestTokenize:
    """分词测试"""

    def test_chinese(self):
        tokens = _tokenize("蓝牙耳机续航")
        assert "蓝" in tokens
        assert "牙" in tokens

    def test_english(self):
        tokens = _tokenize("bluetooth earphone battery")
        assert "bluetooth" in tokens
        assert "earphone" in tokens

    def test_mixed(self):
        tokens = _tokenize("蓝牙5.3 earphone")
        assert "蓝" in tokens
        assert "earphone" in tokens

    def test_empty(self):
        assert _tokenize("") == []
