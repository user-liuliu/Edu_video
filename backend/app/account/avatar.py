from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_AVATAR_PIXELS = 20_000_000
MAX_AVATAR_SIZE = (512, 512)
SUPPORTED_AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}


def normalize_avatar(data: bytes) -> bytes:
    if not data or len(data) > MAX_AVATAR_BYTES:
        raise ValueError("头像文件不能为空且不能超过 2 MiB")

    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in SUPPORTED_AVATAR_FORMATS:
                raise ValueError("头像仅支持 JPG、PNG 或 WebP 格式")
            if getattr(source, "is_animated", False) or getattr(source, "n_frames", 1) != 1:
                raise ValueError("头像不能使用动画图片")
            if source.width * source.height > MAX_AVATAR_PIXELS:
                raise ValueError("头像像素尺寸过大")
            source.verify()

        with Image.open(BytesIO(data)) as source:
            source.load()
            has_alpha = "A" in source.getbands() or "transparency" in source.info
            oriented = ImageOps.exif_transpose(source)
            oriented.thumbnail(MAX_AVATAR_SIZE, Image.Resampling.LANCZOS)
            image = oriented.convert("RGBA" if has_alpha else "RGB")
            image.info.clear()
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError, UnidentifiedImageError) as error:
        raise ValueError("无法读取图片，请重新选择头像") from error
