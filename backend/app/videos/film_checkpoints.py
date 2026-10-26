"""Immutable per-module objects; only verified contiguous prefixes are resumable."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .cache import cache_fingerprint
from .film_modules import FILM_MODULE_PROTOCOL, validate_film, _validate_connections
from .media_assets import read_asset

CHECKPOINT_PROTOCOL = 'film-checkpoints-1'
BATCH_MODULES = 2


def generation_fingerprint(request, writer_fingerprint, runtime):
    # Database UUIDs change when retry creates a new version; render keys do not.
    identities = {str(t['id']): t['render_key'] for t in request['segments'] if 'id' in t}
    def stable(value, field=None):
        if isinstance(value, dict):return {k:stable(v,k) for k,v in value.items()}
        if isinstance(value, list):return [stable(item,field) for item in value]
        if isinstance(value, str) and field in ('id','from_id','to_id'):
            return identities.get(value,value)
        return value
    policy = Path(__file__).with_name('film_modules_prompt.txt').read_bytes()
    return cache_fingerprint({'protocol':CHECKPOINT_PROTOCOL,'request':stable(request),
        'writer':writer_fingerprint,'runtime':runtime,'policy':hashlib.sha256(policy).hexdigest()})


class FilmCheckpoints:
    def __init__(self, storage, request, fingerprint, index, publish, persist):
        self.storage, self.targets, self.fingerprint = storage, request['segments'], fingerprint
        self.index, self.publish, self.persist = deepcopy(index), publish, persist
        self.bundle = None

    async def _read(self, ref):
        return json.loads(await read_asset(self.storage,ref['key'],ref['hash'],'film_modules'))

    async def _put(self, name, value):
        data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
        key,digest=await self.publish(name,data,'application/json')
        ref={'key':key,'hash':digest}
        # Do not advertise a completed checkpoint until its bytes are readable.
        if await self._read(ref)!=value:raise ValueError('动画检查点保存校验失败')
        return ref

    async def restore(self):
        index=self.index
        if not isinstance(index,dict) or index.get('protocol')!=CHECKPOINT_PROTOCOL or index.get('fingerprint')!=self.fingerprint or index.get('total')!=len(self.targets):
            self.index=None
            return None
        try:
            parts=index['parts']
            if not isinstance(parts,list) or not 1<=len(parts)<=len(self.targets):raise ValueError('invalid checkpoint count')
            shared=await self._read(index['shared'])
            bundle={**shared,'segments':[],'transitions':[]}
        except (KeyError,ValueError,TypeError,UnicodeError,OSError):
            self.index=None
            await self.persist(None)
            return None
        for position,ref in enumerate(parts):
            try:
                part=await self._read(ref)
                candidate={**bundle,'segments':bundle['segments']+[part['segment']],
                    'transitions':bundle['transitions']+([part['transition']] if position else [])}
                if position==0 and part.get('transition') is not None:raise ValueError('unexpected first join')
                bundle=_validate_connections(validate_film(candidate,self.targets[:position+1]),self.targets[:position+1])
            except (KeyError,ValueError,TypeError,UnicodeError,OSError):
                break
        count=len(bundle['segments'])
        if count<len(parts):
            self.index={**index,'parts':parts[:count]} if count else None
            await self.persist(self.index)
        self.bundle=bundle if count else None
        return deepcopy(self.bundle)

    async def save(self, value):
        count=len(value.get('segments',[]))
        if not 1<=count<=len(self.targets):raise ValueError('动画检查点片段范围无效')
        bundle=_validate_connections(validate_film(value,self.targets[:count]),self.targets[:count])
        old=self.bundle
        if old and (any(bundle[k]!=old[k] for k in ('shared_html','shared_code'))
                    or bundle['segments'][:len(old['segments'])]!=old['segments']
                    or bundle['transitions'][:len(old['transitions'])]!=old['transitions']):
            raise ValueError('动画续跑不能改变已经保存的片段或共享资源')
        if old and count<len(old['segments']):raise ValueError('动画检查点不能倒退')
        index=deepcopy(self.index) if self.index else {
            'protocol':CHECKPOINT_PROTOCOL,'module_protocol':FILM_MODULE_PROTOCOL,
            'fingerprint':self.fingerprint,'total':len(self.targets),
            'shared':await self._put('checkpoint_shared',{k:bundle[k] for k in ('shared_html','shared_code')}),
            'parts':[]}
        for position in range(len(index['parts']),count):
            part={'segment':bundle['segments'][position],
                  'transition':bundle['transitions'][position-1] if position else None}
            index['parts'].append(await self._put(f'checkpoint_part_{position}',part))
            await self.persist(deepcopy(index))
            self.index=deepcopy(index)
            self.bundle={**bundle,'segments':deepcopy(bundle['segments'][:position+1]),
                'transitions':deepcopy(bundle['transitions'][:position])}
        if self.bundle is None:
            self.index,self.bundle=index,deepcopy(bundle)

