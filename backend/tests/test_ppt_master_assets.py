from io import BytesIO
import pytest
from PIL import Image
from app.presentations.master_assets import normalize_image, image_descriptor
from app.presentations.master_runtime import MasterError

def png(size=(320,180)):
    stream=BytesIO();Image.new('RGB',size,'green').save(stream,format='PNG');return stream.getvalue()

def test_normalized_reference_image_is_bounded_and_descriptor_has_no_bytes():
    data=normalize_image(png((2000,1000)))
    with Image.open(BytesIO(data)) as im:assert im.size==(1600,800)
    descriptor=image_descriptor('owned-material',3,data)
    assert descriptor['name'].endswith('.png') and len(descriptor['sha256'])==64
    assert 'data' not in descriptor

def test_image_pixel_limit_is_enforced_before_decode():
    with pytest.raises(MasterError):normalize_image(png((3000,3000)))
