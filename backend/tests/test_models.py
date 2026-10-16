import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


async def test_username_unique_case_insensitive(db, make_user):
    await make_user("Teacher_Wang")
    with pytest.raises(IntegrityError):
        await make_user("teacher_wang")


async def test_user_defaults(db):
    u = User(username="x1", password_hash="h")
    db.add(u)
    await db.commit()
    assert (u.role, u.status, u.session_version) == ("teacher", "pending", 1)
