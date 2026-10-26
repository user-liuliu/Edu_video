"""PPT search uses the administrator's shared creation-form policy."""
from app.model_configs import resolve
from app.purposes import Purpose
from app.settings_store import get_form_fields

async def search_policy(db,box):
    field=next(f for f in (await get_form_fields(db)).fields if f.key=='web_search')
    available=await resolve(db,box,Purpose.web_search) is not None
    return {'search_available':available,'search_visible':field.visible and available,'search_default':field.default is True and available}

def effective_search(policy,requested=None):
    return policy['search_available'] and (requested if policy['search_visible'] and requested is not None else policy['search_default'])
