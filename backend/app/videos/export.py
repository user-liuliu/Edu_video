import json
import math
import os
import shutil
import subprocess

def executable(name):
    found=os.environ.get('EV_'+name.upper()) or shutil.which(name)
    if found: return found
    if name=='ffmpeg':
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    raise ValueError('视频检查工具尚未安装')


def validate_probe(info,dimensions=None):
    try:
        streams=info['streams']
        video=next(s for s in streams if s['codec_type']=='video')
        audio=next(s for s in streams if s['codec_type']=='audio')
        duration=float(info['format']['duration'])
        size=(int(video['width']),int(video['height']))
        if video['codec_name']!='h264' or audio['codec_name']!='aac' or not math.isfinite(duration) or not 0<duration<=7200 or (dimensions and size!=dimensions): raise ValueError
    except (KeyError,TypeError,ValueError,StopIteration): raise ValueError('视频编码、尺寸或音轨检查失败') from None
    result={'duration':duration,'width':size[0],'height':size[1]}
    if video.get('nb_frames') and video.get('avg_frame_rate'):
        try:
            numerator,denominator=map(float,video['avg_frame_rate'].split('/'))
            result['video_duration']=int(video['nb_frames'])*denominator/numerator
        except (ValueError,ZeroDivisionError): pass
    return result


def probe(path,dimensions=None):
    result=subprocess.run([executable('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,timeout=45)
    if result.returncode: raise ValueError('视频元数据检查失败')
    return validate_probe(json.loads(result.stdout),dimensions)


def decode_check(path):
    result=subprocess.run([executable('ffmpeg'),'-nostdin','-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=180)
    if result.returncode or result.stderr: raise ValueError('视频未通过完整解码检查')


