"""多语言 NLP 预处理层测试

覆盖模块①核心能力：
- 语言识别（8 种语言）
- 文本归一化（NFKC + 空白符）
- 跨语言语义对齐
- 分区路由（en/ja/de → 对应分区，其余 → default）
"""
import pytest
from app.rag.multilingual import (
    detect_language, normalize_text, get_partition,
    preprocess_query, PARTITION_DEFAULT,
)


class TestDetectLanguage:
    """语言识别测试"""

    def test_english(self):
        assert detect_language("How long is the battery life?") == "en"

    def test_chinese(self):
        assert detect_language("耳机的续航时间是多久？") == "zh"

    def test_japanese(self):
        assert detect_language("電池の持ち時間はどのくらいですか？") == "ja"

    def test_german(self):
        assert detect_language("Wie lange dauert der Akku?") == "de"

    def test_empty_string(self):
        result = detect_language("")
        assert result in ("en", "zh", "unknown")

    def test_mixed_language(self):
        # 混合语言应识别出主要语言
        result = detect_language("Hello, 我的耳机 broken")
        assert result in ("en", "zh")


class TestNormalizeText:
    """文本归一化测试"""

    def test_normalizes_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_normalizes_fullwidth(self):
        # 全角字母转半角
        result = normalize_text("Ｈｅｌｌｏ")
        assert "Hello" in result or "HELLO" in result.upper()

    def test_empty_string(self):
        assert normalize_text("") == ""


class TestGetPartition:
    """分区路由测试"""

    def test_english_partition(self):
        assert get_partition("en") == "en"

    def test_japanese_partition(self):
        assert get_partition("ja") == "ja"

    def test_german_partition(self):
        assert get_partition("de") == "de"

    def test_other_language_default(self):
        assert get_partition("es") == PARTITION_DEFAULT

    def test_french_default(self):
        assert get_partition("fr") == PARTITION_DEFAULT


class TestPreprocessQuery:
    """端到端预处理测试"""

    def test_english_query(self):
        result = preprocess_query("How long is the battery life?", lang="en")
        assert "aligned" in result
        assert "partition" in result
        assert "lang" in result
        assert result["partition"] == "en"

    def test_japanese_query(self):
        result = preprocess_query("電池の持ち時間は？", lang="ja")
        assert result["partition"] == "ja"

    def test_specified_lang_overrides_detection(self):
        # 显式指定 lang 应优先于自动检测
        result = preprocess_query("Hello world", lang="ja")
        assert result["partition"] == "ja"

    def test_empty_query(self):
        result = preprocess_query("", lang="en")
        assert result is not None
