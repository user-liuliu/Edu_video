import io
import wave

def wav():
    output=io.BytesIO()
    with wave.open(output,'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(bytes(96000))
    return output.getvalue()

class Store:
    def __init__(self):self.files={}
    def put(self,key,data,content_type=''):self.files[key]=data
    def get(self,key):return self.files[key]
    def ensure_bucket(self):pass
    def stat(self,key):return len(self.files[key])
    def open(self,key,offset=0,length=0):
        class Stream(io.BytesIO):
            def release_conn(self):pass
        return Stream(self.files[key][offset:offset+length] if length else self.files[key][offset:])

class Renderer:
    def __init__(self):self.fail=False

def external_fakes(monkeypatch,store,renderer):
    from app.videos.speech import Narration
    counts={'speech':0,'scene':0}
    async def expression(config,snapshot,targets,http):
        return {'visual_prompt':'统一画布','segments':[{**t,'visual_prompt':'承接前后画面','transition_in':'保留主体','transition_out':'保留主体'} for t in targets]}
    async def speech(config,text,*args,**kwargs):
        counts['speech']+=1
        return Narration(wav(),[{'start':0.,'end':1.,'text':text}])
    monkeypatch.setattr('app.videos.expression.build_expression',expression)
    monkeypatch.setattr('app.videos.pipeline.synthesize_narration',speech)
    monkeypatch.setattr('app.videos.pipeline.MaterialStorage',lambda settings:store)
    monkeypatch.setattr('app.videos.pipeline.RendererClient',lambda *args,**kwargs:renderer)
    return counts
