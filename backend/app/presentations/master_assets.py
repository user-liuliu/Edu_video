"""Private reference image extraction. Original objects remain the sole binary authority."""
import asyncio
from hashlib import sha256
from io import BytesIO
from PIL import Image, ImageOps
from sqlalchemy import select
from app.materials.parsers import parse_document
from app.materials.storage import MaterialStorage
from .models import PptMaterial
from .master_runtime import MasterError

def normalize_image(data):
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width*source.height>8_000_000 or getattr(source,'n_frames',1)!=1:raise MasterError('参考图片过大或为动图，请使用不超过800万像素的静态图片')
            image=ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((1600,1600))
            stream=BytesIO();image.save(stream,format='PNG',optimize=True)
        value=stream.getvalue()
        if len(value)>3*1024*1024:raise MasterError('参考图片压缩后仍过大，请缩小图片')
        return value
    except MasterError:raise
    except Exception as exc:raise MasterError('无法读取参考图片') from exc

def image_descriptor(material_id,index,data):
    digest=sha256(data).hexdigest()
    name=sha256((str(material_id)+':'+str(index)+':'+digest).encode()).hexdigest()[:24]+'.png'
    with Image.open(BytesIO(data)) as image:w,h=image.size
    return {'material_id':str(material_id),'chunk_index':index,'sha256':digest,'name':name,'width':w,'height':h}

async def load_assets(db,project,settings,needed=None,*,pages=None):
    rows=(await db.scalars(select(PptMaterial).where(PptMaterial.project_id==project.id,PptMaterial.owner_id==project.owner_id))).all()
    from .graphics import generated_assets
    result=await generated_assets(project.pages if pages is None else pages,settings,needed);total=sum(map(len,result.values()))
    for material in rows:
        descriptors=[c['image'] for c in material.chunks if c.get('image') and (needed is None or c['image']['name'] in needed)]
        if not descriptors:continue
        blob=await asyncio.to_thread(MaterialStorage(settings).get,material.object_key)
        chunks=await asyncio.to_thread(parse_document,material.filename,blob,settings.temp_dir)
        for descriptor in descriptors:
            index=descriptor['chunk_index']
            if descriptor['material_id']!=str(material.id) or index<0 or index>=len(chunks) or not chunks[index].get('image'):raise MasterError('参考图片索引已变化，请重新生成课件')
            data=await asyncio.to_thread(normalize_image,chunks[index]['image'])
            if image_descriptor(material.id,index,data)!=descriptor:raise MasterError('参考图片内容已变化，请重新上传')
            total+=len(data)
            if len(result)>=20 or total>16*1024*1024:raise MasterError('参考配图最多20张，累计不能超过16MiB')
            if descriptor['name'] in result and result[descriptor['name']]!=data:raise MasterError('图片名称冲突')
            result[descriptor['name']]=data
    if needed is not None and not set(needed)<=set(result):raise MasterError('课件引用的图片已不可用，请重新生成')
    return result

def page_images(pages):
    import xml.etree.ElementTree as ET
    from pathlib import PurePosixPath
    names=set()
    for page in pages:
        if page.get('renderer'):
            root=ET.fromstring(page['svg'])
            names.update(PurePosixPath(n.get('href','')).name for n in root.iter('{http://www.w3.org/2000/svg}image'))
    return names
