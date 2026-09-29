# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_ssl_connection_params.py
"""Regression tests: SQL Server TLS settings must reach the ODBC connection string.

``build_connection_string()`` is the only place ``pyodbc`` gets its
configuration, so anything the config exposes for TLS has to appear there.
"""

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


def make_config(**kwargs):
    defaults = dict(host="db.example.com", database="test_db", username="sa", password="secret")
    defaults.update(kwargs)
    return SQLServerConnectionConfig(**defaults)


def test_encryption_is_on_by_default():
    assert "Encrypt=yes" in make_config().build_connection_string()
    assert "TrustServerCertificate=no" in make_config().build_connection_string()


def test_encrypt_can_be_disabled():
    conn_str = make_config(encrypt=False).build_connection_string()
    assert "Encrypt=no" in conn_str


def test_trust_server_certificate_is_forwarded():
    conn_str = make_config(trust_server_certificate=True).build_connection_string()
    assert "TrustServerCertificate=yes" in conn_str


def test_client_certificate_is_forwarded():
    conn_str = make_config(
        client_certificate="/certs/client.pem",
        client_key="/certs/client.key",
    ).build_connection_string()
    assert "ClientCertificate=/certs/client.pem" in conn_str
    assert "ClientKey=/certs/client.key" in conn_str


def test_host_name_in_certificate_is_forwarded():
    """Needed when the server certificate CN is not the connect host."""
    conn_str = make_config(host_name_in_certificate="db.internal").build_connection_string()
    assert "HostNameInCertificate=db.internal" in conn_str


def test_client_key_password_is_forwarded():
    conn_str = make_config(
        client_certificate="/certs/client.pfx",
        client_key_password="pfx-secret",
    ).build_connection_string()
    assert "ClientKeyPassword=pfx-secret" in conn_str


def test_no_client_tls_keys_when_unset():
    conn_str = make_config().build_connection_string()
    for key in ("ClientCertificate", "ClientKey", "ClientKeyPassword", "HostNameInCertificate"):
        assert key not in conn_str


def test_client_key_without_certificate_is_rejected():
    with pytest.raises(ValueError, match="client_key requires client_certificate"):
        make_config(client_key="/certs/client.key").validate_config()
