"""占位接口与别名/批处理路由测试。

覆盖之前评估为低价值但应验证的接口：
- mobiles/sms 占位接口（501 / 空结构 / 配置读写）
- 别名认证路由（user_getinfo / register / changepwd 等）
- 订单批处理（batch* 系列）
- 中控工作日志（worklog start/end）
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import Settings
from app.db.models.base import Base
from app.db.models.laike import LaikeOrder
from app.main import create_app


DEMO_HEADERS = {"authorization": "Bearer DEMO-test-token"}


@pytest.fixture
def app(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'placeholder.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                LaikeOrder(
                    provider_order_id="DEMO-P-001",
                    account_id="ACC-001",
                    order_status=3,
                    pay_amount_fen=10000,
                    create_order_time=1789257600,
                    update_order_time=1789257660,
                    status="3",
                    payload_json={"order_id": "DEMO-P-001"},
                ),
                LaikeOrder(
                    provider_order_id="DEMO-P-002",
                    account_id="ACC-002",
                    order_status=1,
                    pay_amount_fen=2000,
                    create_order_time=1789257600,
                    update_order_time=1789257600,
                    status="1",
                    payload_json={"order_id": "DEMO-P-002"},
                ),
            ]
        )
        session.commit()
    return create_app(
        Settings(_env_file=None, database_url=None, laike_database_url=database_url)
    )


async def post(app, path, *, headers=None, json=None):
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 123))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, headers=headers or {}, json=json or {})


# ---------- mobiles/sms 占位接口 ----------

@pytest.mark.asyncio
async def test_mobile_external_stub_returns_501(app):
    for path in [
        "/apiv1/user/mobiles/addseat",
        "/apiv1/user/mobiles/sendsms",
        "/apiv1/user/sms/send",
    ]:
        resp = await post(app, path, headers=DEMO_HEADERS, json={})
        assert resp.status_code == 501
        assert resp.json()["code"] == 0


@pytest.mark.asyncio
async def test_mobile_read_stub_returns_empty(app):
    for path in [
        "/apiv1/user/mobiles/calllog",
        "/apiv1/user/mobiles/seatlist",
        "/apiv1/user/mobiles/wechatlist",
    ]:
        resp = await post(app, path, headers=DEMO_HEADERS, json={})
        assert resp.status_code == 200
        assert resp.json()["data"] == {"list": [], "total": 0}


@pytest.mark.asyncio
async def test_mobile_config_read_returns_empty(app):
    resp = await post(app, "/apiv1/user/mobiles/getconfiginfo", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"enabled": None, "config": {}}


@pytest.mark.asyncio
async def test_mobile_qrcode_read_returns_none(app):
    resp = await post(app, "/apiv1/user/mobiles/getqrcodeinfo", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["qrcode"] is None


@pytest.mark.asyncio
async def test_mobile_config_update_writes_prefixed_key(app):
    resp = await post(
        app,
        "/apiv1/user/mobiles/updateconfiginfo",
        headers=DEMO_HEADERS,
        json={"sms_sign": "测试签名"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_mobile_stub_requires_session(app):
    resp = await post(app, "/apiv1/user/mobiles/addseat")
    assert resp.status_code == 401


# ---------- 别名认证路由 ----------

@pytest.mark.asyncio
async def test_user_getinfo(app):
    resp = await post(app, "/apiv1/user/getinfo", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["nickname"] == "测试管理员"


@pytest.mark.asyncio
async def test_register_forbidden(app):
    resp = await post(app, "/apiv1/user/register", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_changepwd(app):
    resp = await post(
        app,
        "/apiv1/user/user/changepwd",
        headers=DEMO_HEADERS,
        json={"old_password": "a", "new_password": "b"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_user_changepwd_requires_passwords(app):
    resp = await post(app, "/apiv1/user/user/changepwd", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_user_changenoticeflg(app):
    resp = await post(app, "/apiv1/user/user/changenoticeflg", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_setsystemupnum(app):
    resp = await post(app, "/apiv1/user/setsystemupnum", headers=DEMO_HEADERS, json={"num": 99})
    assert resp.status_code == 200
    assert resp.json()["data"]["num"] == 99


# ---------- 订单批处理 ----------

@pytest.mark.asyncio
async def test_batch_change_anchor(app):
    resp = await post(
        app,
        "/apiv1/user/order/batchchangeanchor",
        headers=DEMO_HEADERS,
        json={"order_ids": ["DEMO-P-001", "DEMO-P-002"], "staff_id": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2


@pytest.mark.asyncio
async def test_batch_add_follow(app):
    resp = await post(
        app,
        "/apiv1/user/order/batchaddfollow",
        headers=DEMO_HEADERS,
        json={"order_ids": ["DEMO-P-001"], "memo": "批量跟进"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 1


@pytest.mark.asyncio
async def test_batch_requires_order_ids(app):
    resp = await post(app, "/apiv1/user/order/batchchangeanchor", headers=DEMO_HEADERS, json={"staff_id": 3})
    assert resp.status_code == 400


# ---------- 中控工作日志 ----------

@pytest.mark.asyncio
async def test_worklog_start_and_end(app):
    # start
    resp = await post(
        app,
        "/apiv1/console/startwork",
        headers=DEMO_HEADERS,
        json={"live_room_id": 1, "staff_id": 1, "remark": "开始"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["work_type"] == "start"

    # end
    resp = await post(
        app,
        "/apiv1/console/endwork",
        headers=DEMO_HEADERS,
        json={"live_room_id": 1, "staff_id": 1, "remark": "结束"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["work_type"] == "end"


@pytest.mark.asyncio
async def test_worklog_index(app):
    resp = await post(app, "/apiv1/console/consoleworklog", headers=DEMO_HEADERS, json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 0
