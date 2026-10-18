"""模型用途：每种用途对应一条模型配置（model_configs 表的主键）。"""

from enum import StrEnum


class Purpose(StrEnum):
    outline_llm = "outline_llm"
    review_llm = "review_llm"
    vision_llm = "vision_llm"
    embedding = "embedding"
    tts = "tts"
    web_search = "web_search"


# 给老师看的中文名称
PURPOSE_LABELS: dict[Purpose, str] = {
    Purpose.outline_llm: "写大纲/讲稿",
    Purpose.review_llm: "审核",
    Purpose.vision_llm: "看图识别",
    Purpose.embedding: "Embedding",
    Purpose.tts: "配音",
    Purpose.web_search: "联网搜索",
}

# 生成视频前必须配置好的用途
REQUIRED_PURPOSES: frozenset[Purpose] = frozenset(
    {
        Purpose.outline_llm,
        Purpose.review_llm,
        Purpose.vision_llm,
        Purpose.tts,
    }
)
