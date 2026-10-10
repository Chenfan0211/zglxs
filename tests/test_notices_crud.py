"""公告（SystemNotice）模块完整 CRUD 测试。

notices 模块此前完全无测试覆盖，本文件补齐 list/get/create/update/delete。
注意：GET 接口走 loopback 校验，POST/PUT/DELETE 走演示会话鉴权。
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.system import SystemNotice
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def notice_app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'notice.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                SystemNotice(title="公告一", content="内容一", is_published=True),
                SystemNotice(title="公告二", content="内容二", is_published=False),
            ]
        )
        session.commit()
    return create_app(
        Settings(_env_file=None, database_url=None, laike_database_url=database_url)
    )


async def request(app, method, path, *, headers=None, json=None):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers or {}, json=json or {})


@pytest.mark.asyncio
async def test_notice_list_only_published_by_default(notice_app):
    resp = await request(notice_app, "GET", "/api/notices")
    assert resp.status_code == 200
    body = resp.json()["data"]["list"]
    assert len(body) == 1  # 只返回已发布的公告一
    assert body[0]["title"] == "公告一"


@pytest.mark.asyncio
async def test_notice_list_include_all(notice_app):
    resp = await request(notice_app, "GET", "/api/notices?all=1")
    assert resp.status_code == 200
    body = resp.json()["data"]["list"]
    assert len(body) == 2


@pytest.mark.asyncio
async def test_notice_get_by_id(notice_app):
    resp = await request(notice_app, "GET", "/api/notices/1")
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "公告一"


@pytest.mark.asyncio
async def test_notice_get_not_found(notice_app):
    resp = await request(notice_app, "GET", "/api/notices/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_notice_create(notice_app):
    resp = await request(
        notice_app,
        "POST",
        "/api/notices",
        headers=DEMO_HEADERS,
        json={"title": "新公告", "content": "新内容", "notice_type": "system"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 1
    assert resp.json()["data"]["title"] == "新公告"


@pytest.mark.asyncio
async def test_notice_create_requires_title_content(notice_app):
    resp = await request(notice_app, "POST", "/api/notices", headers=DEMO_HEADERS, json={"title": "只有标题"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_notice_update(notice_app):
    resp = await request(
        notice_app,
        "PUT",
        "/api/notices/1",
        headers=DEMO_HEADERS,
        json={"title": "公告一改", "is_published": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "公告一改"
    assert resp.json()["data"]["is_published"] is False


@pytest.mark.asyncio
async def test_notice_update_not_found(notice_app):
    resp = await request(notice_app, "PUT", "/api/notices/999", headers=DEMO_HEADERS, json={"title": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_notice_delete(notice_app):
    resp = await request(notice_app, "DELETE", "/api/notices/1", headers=DEMO_HEADERS)
    assert resp.status_code == 200

    # 删除后查询 404
    resp = await request(notice_app, "GET", "/api/notices/1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_notice_write_requires_session(notice_app):
    resp = await request(notice_app, "POST", "/api/notices", json={"title": "x", "content": "y"})
    assert resp.status_code == 401
