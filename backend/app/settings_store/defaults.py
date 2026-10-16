"""新建视频页面的默认配置（库里还没有保存过时使用）。"""

from .schemas import FieldConfig, FieldKey, FieldOption, FormFieldsConfig


def _opts(*pairs: tuple[str, str]) -> list[FieldOption]:
    return [FieldOption(value=v, label=label) for v, label in pairs]


def _same(*values: str) -> list[FieldOption]:
    """value 和 label 相同的选项。"""
    return [FieldOption(value=v, label=v) for v in values]


DEFAULT_FORM_FIELDS = FormFieldsConfig(
    fields=[
        FieldConfig(key=FieldKey.prompt, label="想讲什么", visible=True, default=None),
        # 允许的文件类型由第 2 部分决定
        FieldConfig(key=FieldKey.materials, label="参考素材", visible=True, default=None),
        FieldConfig(
            key=FieldKey.subject,
            label="科目",
            visible=True,
            default="数学",
            options=_same(
                "数学", "物理", "化学", "生物", "语文", "英语", "历史", "地理", "道德与法治"
            ),
        ),
        FieldConfig(
            key=FieldKey.grade,
            label="年级",
            visible=True,
            default="初三",
            options=_same(
                "一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
                "初一", "初二", "初三", "高一", "高二", "高三",
            ),
        ),
        FieldConfig(
            key=FieldKey.textbook_edition,
            label="教材版本",
            visible=True,
            default="人教版",
            options=[
                *_same("人教版", "北师大版", "苏教版", "沪教版"),
                FieldOption(value="统编版", label="统编版", subjects=["语文", "历史", "道德与法治"]),
            ],
            default_by_subject={"语文": "统编版", "历史": "统编版", "道德与法治": "统编版"},
        ),
        FieldConfig(
            key=FieldKey.duration,
            label="视频时长",
            visible=True,
            default="5",
            options=_opts(("3", "3 分钟"), ("5", "5 分钟"), ("10", "10 分钟"), ("custom", "自定义")),
        ),
        FieldConfig(
            key=FieldKey.aspect_ratio,
            label="视频尺寸",
            visible=True,
            default="16:9",
            options=_opts(("16:9", "16:9 横屏"), ("9:16", "9:16 竖屏"), ("1:1", "1:1 方形")),
        ),
        FieldConfig(
            key=FieldKey.style,
            label="讲解风格",
            visible=True,
            default="auto",
            options=_opts(
                ("auto", "按科目自动"),
                ("math_animation", "数学动画"),
                ("story_sketch", "故事 / 简笔画"),
            ),
        ),
        # 可选的音色来自模型配置里的 tts 一项
        FieldConfig(key=FieldKey.voice, label="配音声音", visible=True, default=None),
        FieldConfig(key=FieldKey.web_search, label="允许联网搜索", visible=True, default=True),
    ]
)
