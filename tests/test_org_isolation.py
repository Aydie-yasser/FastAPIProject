"""Organization isolation: no cross-org access without membership."""

from tests.conftest import auth_headers, create_org, login_token, register_user


def test_admin_of_org_a_cannot_read_org_b_audit_logs(client):
    register_user(client, "iso_alice@example.com")
    register_user(client, "iso_bob@example.com")
    alice_t = login_token(client, "iso_alice@example.com")
    bob_t = login_token(client, "iso_bob@example.com")
    org_a = create_org(client, alice_t, "Company A")
    org_b = create_org(client, bob_t, "Company B")

    r = client.get(
        f"/organizations/{org_b}/audit-logs",
        headers=auth_headers(alice_t),
    )
    assert r.status_code == 403


def test_items_stay_inside_org(client):
    register_user(client, "iso_items_a@example.com")
    register_user(client, "iso_items_b@example.com")
    a_t = login_token(client, "iso_items_a@example.com")
    b_t = login_token(client, "iso_items_b@example.com")
    org_a = create_org(client, a_t, "Items A")
    org_b = create_org(client, b_t, "Items B")

    client.post(
        f"/organizations/{org_a}/item",
        json={"item_details": {"sku": "A-1"}},
        headers=auth_headers(a_t),
    )
    r = client.get(
        f"/organizations/{org_b}/item",
        headers=auth_headers(a_t),
    )
    assert r.status_code == 403

    r_ok = client.get(
        f"/organizations/{org_a}/item",
        headers=auth_headers(a_t),
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["total"] >= 1
