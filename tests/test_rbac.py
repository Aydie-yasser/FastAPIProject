"""RBAC: org admin vs member — only admins may access audit logs (and similar)."""

from tests.conftest import auth_headers, create_org, login_token, register_user


def test_member_cannot_list_audit_logs(client):
    register_user(client, "rbac_admin@example.com", name="Admin")
    register_user(client, "rbac_member@example.com", name="Member")
    admin_t = login_token(client, "rbac_admin@example.com")
    org_id = create_org(client, admin_t, "RBAC Org")

    r_add = client.post(
        f"/organizations/{org_id}/user",
        json={"email": "rbac_member@example.com", "role": "member"},
        headers=auth_headers(admin_t),
    )
    assert r_add.status_code == 201, r_add.text

    member_t = login_token(client, "rbac_member@example.com")
    r = client.get(
        f"/organizations/{org_id}/audit-logs",
        headers=auth_headers(member_t),
    )
    assert r.status_code == 403


def test_admin_can_list_audit_logs(client):
    register_user(client, "rbac_admin2@example.com")
    token = login_token(client, "rbac_admin2@example.com")
    org_id = create_org(client, token, "Admin Logs Org")
    r = client.get(
        f"/organizations/{org_id}/audit-logs",
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body


def test_member_cannot_add_users(client):
    register_user(client, "owner3@example.com")
    register_user(client, "outsider3@example.com")
    owner_t = login_token(client, "owner3@example.com")
    org_id = create_org(client, owner_t, "Invite Org")
    client.post(
        f"/organizations/{org_id}/user",
        json={"email": "outsider3@example.com", "role": "member"},
        headers=auth_headers(owner_t),
    )
    member_t = login_token(client, "outsider3@example.com")
    register_user(client, "newperson3@example.com")
    r = client.post(
        f"/organizations/{org_id}/user",
        json={"email": "newperson3@example.com", "role": "member"},
        headers=auth_headers(member_t),
    )
    assert r.status_code == 403
