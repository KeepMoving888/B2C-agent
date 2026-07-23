"""多语言 NLP 预处理与跨语言语义对齐层

解决多语言客服场景下跨语言检索召回率低的核心难题：
1. 语言识别：基于 Unicode 脚本范围 + 变音特征识别，无需第三方依赖
2. 文本归一化：NFKC 全角→半角、大小写、标点统一、控制字符与多余空白清理
3. 跨语言语义对齐：借助 BGE-M3 多语言嵌入空间，将多语言 query 统一映射到
   中文(pivot)语义空间检索；在线模式对 query 回译至 pivot 增强对齐
4. 语料分区路由：高频语言(英/日/德)优先检索自身镜像分区，不足时回退 pivot 分区
"""
import re
import unicodedata
from typing import Tuple

from loguru import logger

from app.config import settings

PIVOT_LANG = "zh"
PARTITION_DEFAULT = "default"

# 德语变音特征（拉丁语系细分用）
_RE_DE = re.compile(r"[äöüÄÖÜß]")
# 德语高频功能词（无变音时辅助识别）
_DE_KEYWORDS = {
    "der", "die", "das", "ist", "nicht", "und", "wie", "lange",
    "dauert", "akku", "meine", "bestellung", "refund", "rück",
    "wann", "wird", "geliefert", "haben", "sie", "ich", "möchte",
    "mit", "auf", "für", "ein", "eine", "von", "zu",
}
# 日文假名 Unicode 范围
_HIRAGANA = range(0x3040, 0x30A0)
_KATAKANA = range(0x30A0, 0x3100)


def _partition_langs() -> set:
    """从配置加载高频语言分区集合"""
    raw = getattr(settings, "language_partitions", "") or ""
    return set(x.strip() for x in raw.split(",") if x.strip())


def detect_language(text: str) -> str:
    """基于 Unicode 脚本范围 + 变音特征识别语言（无需第三方依赖）

    Returns:
        语言码 zh/ja/de/en；前端传入的 lang 优先，此函数作兜底
    """
    if not text:
        return "en"
    has_hira = has_kata = cjk = latin = 0
    for ch in text:
        cp = ord(ch)
        if cp in _HIRAGANA:
            has_hira += 1
        elif cp in _KATAKANA:
            has_kata += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0xAC00 <= cp <= 0xD7AF:
            cjk += 1
        elif ch.isalpha():
            latin += 1
    if has_hira or has_kata:
        return "ja"
    if cjk:
        return "zh"
    if _RE_DE.search(text):
        return "de"
    # 无变音时通过高频功能词辅助识别德语
    if latin:
        words = set(w.strip('.,!?;:"\'()').lower() for w in text.split())
        if len(words & _DE_KEYWORDS) >= 2:
            return "de"
        return "en"
    return "en"


def normalize_text(text: str) -> str:
    """文本归一化：NFKC 全角→半角 + 控制字符清理 + 多余空白合并"""
    if not text:
        return ""
    # NFKC：全角字母数字与兼容字符归一化为半角
    text = unicodedata.normalize("NFKC", text)
    # 去除控制字符（保留换行与制表符）
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    # 合并多余空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def align_to_pivot(text: str, src_lang: str) -> Tuple[str, bool]:
    """跨语言语义对齐：将 query 映射到 pivot(中文)语义空间

    策略：
    - src_lang == pivot：直接返回
    - 在线模式(LLM 可用)：回译至 pivot，消除表达习惯差异
    - 离线模式：返回原文，依赖 BGE-M3 多语言嵌入空间的跨语言对齐能力

    Returns:
        (aligned_text, translated)
    """
    pivot = settings.cross_lingual_pivot_lang or PIVOT_LANG
    if src_lang == pivot or not text:
        return text, False
    try:
        from app.services.llm_service import is_llm_available
        if is_llm_available():
            from app.services.translation import translate
            aligned = translate(text, src_lang, pivot)
            if aligned and aligned != text:
                return aligned, True
    except Exception as e:
        logger.debug(f"跨语言对齐回译失败，依赖 BGE-M3 跨语言空间: {e}")
    # 离线/失败：依赖 BGE-M3 多语言嵌入的跨语言对齐能力，直接用原文检索
    return text, False


def get_partition(lang: str) -> str:
    """语料分区路由：高频语言返回自身分区，其余返回 default

    高频语言(en/ja/de)拥有镜像分区，术语级召回更精准；
    其他语言统一走 default 分区(以中文 pivot 语料为主)。
    """
    if not lang:
        return PARTITION_DEFAULT
    if lang in _partition_langs():
        return lang
    return PARTITION_DEFAULT


def preprocess_query(text: str, lang: str = "") -> dict:
    """查询预处理主入口：语言识别 → 归一化 → 跨语言对齐 → 分区路由

    Args:
        text: 原始查询
        lang: 前端传入的业务语言码（优先于脚本识别）

    Returns:
        {original, lang, normalized, aligned, translated, partition}
    """
    original = text or ""
    # 1. 语言识别：前端 lang 优先，缺失时脚本识别兜底
    detected = lang if lang else detect_language(original)
    # 2. 归一化
    normalized = normalize_text(original)
    # 3. 跨语言对齐
    aligned, translated = align_to_pivot(normalized, detected)
    # 4. 分区路由
    partition = get_partition(detected)
    logger.debug(
        f"[multilingual] lang={detected} partition={partition} "
        f"translated={translated} query='{original[:40]}'"
    )
    return {
        "original": original,
        "lang": detected,
        "normalized": normalized,
        "aligned": aligned,
        "translated": translated,
        "partition": partition,
    }