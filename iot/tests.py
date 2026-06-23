"""Tests IoT : endpoints gateway (token), API session, consumer SCADA."""

import json

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from config.asgi import application
from exploitations.models import Exploitation
from iot.models import IotCommand, IotDevice, IotTelemetry
from iot.services import group_name

User = get_user_model()


@pytest.fixture
def device(db):
    user = User.objects.create_user(email="iot@ex.com", password="pwd12345")
    exploitation = Exploitation.objects.create(owner=user, name="Ferme IoT")
    dev = IotDevice.objects.create(
        exploitation=exploitation, name="Débitmètre 1",
        device_type=IotDevice.DeviceType.FLOW_METER, device_id="DEV-001", device_token="tok-secret",
    )
    return user, exploitation, dev


@pytest.mark.django_db
def test_ingest_creates_telemetry_and_marks_online(client, device):
    _, _, dev = device
    resp = client.post(
        "/api/iot/ingest/",
        data=json.dumps({"deviceToken": "tok-secret", "flowRateM3h": 42.5, "pressureBar": 3.1}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    dev.refresh_from_db()
    assert dev.status == IotDevice.Status.ONLINE
    assert IotTelemetry.objects.filter(device=dev, flow_rate_m3h=42.5).exists()


@pytest.mark.django_db
def test_ingest_rejects_bad_token(client, device):
    resp = client.post(
        "/api/iot/ingest/",
        data=json.dumps({"deviceToken": "wrong", "flowRateM3h": 1}),
        content_type="application/json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_command_poll_marks_sent(client, device):
    _, _, dev = device
    IotCommand.objects.create(device=dev, command_type="open_valve")
    resp = client.get("/api/iot/command/poll/", HTTP_X_DEVICE_TOKEN="tok-secret")
    assert resp.status_code == 200
    cmds = resp.json()["commands"]
    assert len(cmds) == 1 and cmds[0]["commandType"] == "open_valve"
    assert IotCommand.objects.get(id=cmds[0]["id"]).status == IotCommand.Status.SENT


@pytest.mark.django_db
def test_command_callback_completes(client, device):
    _, _, dev = device
    cmd = IotCommand.objects.create(device=dev, command_type="open_valve", status=IotCommand.Status.SENT)
    resp = client.post(
        "/api/iot/command/callback/",
        data=json.dumps({"deviceToken": "tok-secret", "commandId": cmd.id, "status": "completed"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    cmd.refresh_from_db()
    assert cmd.status == IotCommand.Status.COMPLETED and cmd.completed_at is not None


@pytest.mark.django_db
def test_device_api_tenant_scoped(client, device):
    user, exploitation, dev = device
    other = User.objects.create_user(email="x@ex.com", password="pwd12345")
    other_exp = Exploitation.objects.create(owner=other, name="Autre")
    IotDevice.objects.create(exploitation=other_exp, name="Z", device_type="generic", device_id="DEV-Z")
    client.force_login(user)
    resp = client.get("/api/devices/")
    assert resp.status_code == 200
    assert {d["device_id"] for d in resp.json()} == {"DEV-001"}


@pytest.mark.django_db(transaction=True)
async def test_scada_consumer_receives_broadcast():
    from channels.db import database_sync_to_async

    def _setup():
        user = User.objects.create_user(email="ws@ex.com", password="pwd12345")
        exploitation = Exploitation.objects.create(owner=user, name="WS Farm")
        return user, exploitation

    user, exploitation = await database_sync_to_async(_setup)()

    communicator = WebsocketCommunicator(application, "/ws/scada/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    hello = await communicator.receive_json_from()
    assert hello["event"] == "connected"

    layer = get_channel_layer()
    await layer.group_send(
        group_name(exploitation.id),
        {"type": "telemetry.message", "payload": {"event": "telemetry", "deviceId": 1, "flowRateM3h": 9.9}},
    )
    msg = await communicator.receive_json_from()
    assert msg["event"] == "telemetry" and msg["flowRateM3h"] == 9.9
    await communicator.disconnect()
