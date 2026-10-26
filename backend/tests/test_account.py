import io

from PIL import Image
from sqlalchemy import select

from app.materials.storage import MaterialStorage
from app.models import ObjectCleanup, User
from app.security import verify_password
from conftest import login


def avatar_bytes(format="JPEG"):
    image = Image.new("RGB", (1200, 800), (34, 112, 92))
    stream = io.BytesIO()
    image.save(stream, format=format)
    return stream.getvalue()


async def test_profile_updates_fields_and_auth_me_returns_them(teacher_client):
    response = await teacher_client.get("/api/account/profile")

    assert response.status_code == 200
    assert response.json()["gender"] == "unspecified"
    assert response.json()["display_name"] is None

    response = await teacher_client.patch(
        "/api/account/profile",
        headers={"Origin": "http://test"},
        json={"display_name": "  王老师  ", "gender": "female", "school": "  海滨中学  "},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "王老师"
    assert response.json()["gender"] == "female"
    assert response.json()["school"] == "海滨中学"
    assert response.json()["avatar_url"] is None

    me = (await teacher_client.get("/api/auth/me")).json()
    assert (me["display_name"], me["gender"], me["school"]) == ("王老师", "female", "海滨中学")
    assert "password_hash" not in me


async def test_profile_rejects_unknown_gender_without_changing_saved_fields(teacher_client):
    await teacher_client.patch(
        "/api/account/profile",
        headers={"Origin": "http://test"},
        json={"display_name": "王老师", "gender": "female"},
    )

    response = await teacher_client.patch(
        "/api/account/profile", headers={"Origin": "http://test"}, json={"gender": "other"}
    )

    assert response.status_code == 422
    profile = (await teacher_client.get("/api/account/profile")).json()
    assert (profile["display_name"], profile["gender"]) == ("王老师", "female")


async def test_password_change_rejects_wrong_current_password(teacher_client, db):
    response = await teacher_client.post(
        "/api/account/password",
        headers={"Origin": "http://test"},
        json={"current_password": "wrongpass", "new_password": "newpass123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_current_password"
    assert (await teacher_client.get("/api/auth/me")).status_code == 200
    user = await db.scalar(select(User).where(User.username == "teacher1"))
    assert verify_password("pass1234", user.password_hash)


async def test_password_change_keeps_request_session_and_revokes_other_sessions(app, teacher_client, make_client):
    previous_session = make_client(app)
    await login(previous_session, "teacher1", "pass1234")

    response = await teacher_client.post(
        "/api/account/password",
        headers={"Origin": "http://test"},
        json={"current_password": "pass1234", "new_password": "newpass123"},
    )

    assert response.status_code == 204
    assert (await teacher_client.get("/api/auth/me")).status_code == 200
    assert (await previous_session.get("/api/auth/me")).status_code == 401

    old_login = make_client(app)
    new_login = make_client(app)
    assert (await old_login.post("/api/auth/login", json={"username": "teacher1", "password": "pass1234"})).status_code == 401
    assert (await new_login.post("/api/auth/login", json={"username": "teacher1", "password": "newpass123"})).status_code == 200


async def test_password_change_rejects_same_password(teacher_client):
    response = await teacher_client.post(
        "/api/account/password",
        headers={"Origin": "http://test"},
        json={"current_password": "pass1234", "new_password": "pass1234"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "password_unchanged"


async def test_avatar_upload_normalizes_image_and_queues_old_object_for_cleanup(
    teacher_client, db, monkeypatch
):
    objects = {}
    monkeypatch.setattr(MaterialStorage, "__init__", lambda self, settings: None)
    monkeypatch.setattr(MaterialStorage, "put", lambda self, key, data, mime: objects.__setitem__(key, (data, mime)))
    monkeypatch.setattr(MaterialStorage, "get", lambda self, key: objects[key][0])
    monkeypatch.setattr(MaterialStorage, "delete", lambda self, key: objects.pop(key, None))

    user = await db.scalar(select(User).where(User.username == "teacher1"))
    user.avatar_key = "users/teacher1/profile/avatar/old.png"
    await db.commit()
    objects[user.avatar_key] = (avatar_bytes("PNG"), "image/png")

    response = await teacher_client.post(
        "/api/account/avatar",
        headers={"Origin": "http://test"},
        files={"file": ("portrait.webp", avatar_bytes("WEBP"), "image/webp")},
    )

    assert response.status_code == 200
    assert response.json()["avatar_url"] == "/api/account/avatar"
    await db.refresh(user)
    new_key = user.avatar_key
    assert new_key in objects
    assert objects[new_key][1] == "image/png"
    stored_image = Image.open(io.BytesIO(objects[new_key][0]))
    assert stored_image.format == "PNG" and stored_image.width <= 512 and stored_image.height <= 512
    assert await db.scalar(select(ObjectCleanup.object_key).where(ObjectCleanup.object_key == "users/teacher1/profile/avatar/old.png"))

    avatar = await teacher_client.get("/api/account/avatar")
    assert avatar.status_code == 200
    assert avatar.headers["content-type"] == "image/png"
    assert avatar.headers["cache-control"] == "no-store"
    assert avatar.headers["x-content-type-options"] == "nosniff"


async def test_avatar_upload_rejects_invalid_image_and_cross_origin_request(teacher_client):
    invalid = await teacher_client.post(
        "/api/account/avatar",
        headers={"Origin": "http://test"},
        files={"file": ("portrait.jpg", b"not an image", "image/jpeg")},
    )
    cross_origin = await teacher_client.post(
        "/api/account/avatar",
        headers={"Origin": "https://attacker.example"},
        files={"file": ("portrait.jpg", avatar_bytes(), "image/jpeg")},
    )

    assert invalid.status_code == 422
    assert cross_origin.status_code == 403


async def test_password_attempts_are_limited_separately_from_login(teacher_client):
    for _ in range(5):
        response = await teacher_client.post(
            "/api/account/password", headers={"Origin": "http://test"},
            json={"current_password": "wrongpass", "new_password": "newpass123"},
        )
        assert response.status_code == 401
    blocked = await teacher_client.post(
        "/api/account/password", headers={"Origin": "http://test"},
        json={"current_password": "pass1234", "new_password": "newpass123"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "password_change_locked"
    assert (await teacher_client.post(
        "/api/auth/login", json={"username": "teacher1", "password": "pass1234"}
    )).status_code == 200


async def test_profile_ownership_and_protected_fields(app, teacher_client, make_client, make_user):
    await make_user("teacher2")
    other = make_client(app)
    await login(other, "teacher2", "pass1234")
    assert (await teacher_client.patch(
        "/api/account/profile", headers={"Origin": "http://test"}, json={"school": "一中"}
    )).status_code == 200
    assert (await other.get("/api/account/profile")).json()["school"] is None
    assert (await teacher_client.patch(
        "/api/account/profile", headers={"Origin": "http://test"}, json={"role": "admin", "username": "renamed"}
    )).status_code == 422
    assert (await teacher_client.get("/api/auth/me")).json()["role"] == "teacher"
    unauthenticated = make_client(app)
    assert (await unauthenticated.get("/api/account/profile")).status_code == 401


async def test_profile_mutations_reject_missing_origin(teacher_client):
    response = await teacher_client.patch("/api/account/profile", json={"display_name": "unexpected"})
    assert response.status_code == 403
    assert (await teacher_client.get("/api/account/profile")).json()["display_name"] is None


async def test_avatar_can_be_restored_to_default(teacher_client, db):
    user = await db.scalar(select(User).where(User.username == "teacher1"))
    user.avatar_key = "users/teacher1/profile/avatar/original.png"
    await db.commit()
    response = await teacher_client.delete("/api/account/avatar", headers={"Origin": "http://test"})
    assert response.status_code == 204
    assert (await teacher_client.get("/api/account/profile")).json()["avatar_url"] is None
    assert (await teacher_client.get("/api/account/avatar")).status_code == 404
    assert await db.scalar(select(ObjectCleanup.object_key).where(ObjectCleanup.object_key == "users/teacher1/profile/avatar/original.png"))


async def test_avatar_storage_failure_preserves_previous_avatar(teacher_client, db, monkeypatch):
    user = await db.scalar(select(User).where(User.username == "teacher1"))
    user.avatar_key = "previous.png"
    await db.commit()
    monkeypatch.setattr(MaterialStorage, "__init__", lambda self, settings: None)
    def fail(*args):
        raise OSError("storage unavailable")
    monkeypatch.setattr(MaterialStorage, "put", fail)
    response = await teacher_client.post(
        "/api/account/avatar", headers={"Origin": "http://test"},
        files={"file": ("portrait.png", avatar_bytes("PNG"), "image/png")},
    )
    assert response.status_code == 503
    await db.refresh(user)
    assert user.avatar_key == "previous.png"


async def test_avatar_upload_enforces_size_limit(teacher_client):
    response = await teacher_client.post(
        "/api/account/avatar", headers={"Origin": "http://test"},
        files={"file": ("portrait.png", b"x" * (2 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413


def test_avatar_normalization_strips_private_metadata_and_orients_image():
    from app.account.avatar import normalize_avatar
    image = Image.new("RGB", (100, 50), (30, 100, 200))
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private description"
    stream = io.BytesIO()
    image.save(stream, format="JPEG", exif=exif)
    normalized = Image.open(io.BytesIO(normalize_avatar(stream.getvalue())))
    assert normalized.size == (50, 100)
    assert not normalized.getexif()


async def test_avatar_corrupt_png_returns_validation_error(teacher_client):
    data = bytearray(avatar_bytes("PNG"))
    index = data.index(b"IDAT")
    length = int.from_bytes(data[index - 4:index], "big")
    data[index + 4 + length] ^= 1
    response = await teacher_client.post(
        "/api/account/avatar", headers={"Origin": "http://test"},
        files={"file": ("corrupt.png", bytes(data), "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_avatar"
