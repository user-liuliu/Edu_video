from sqlalchemy import select

from app.jobs.dispatcher import cleanup_objects
from app.models import ObjectCleanup


class Storage:
    def __init__(self):
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)
        if not key.strip():
            raise ValueError('empty object key')


async def test_cleanup_discards_legacy_empty_object_keys(db):
    db.add_all([ObjectCleanup(object_key=''), ObjectCleanup(object_key='videos/kept.mp4')])
    await db.commit()
    storage = Storage()

    await cleanup_objects(db, storage)

    assert storage.deleted == ['videos/kept.mp4']
    assert (await db.scalars(select(ObjectCleanup))).all() == []
