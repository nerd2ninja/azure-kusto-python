# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License
import pytest

from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.data._token_providers import *
from azure.kusto.data.exceptions import KustoAuthenticationError
from azure.kusto.data.security import _AadHelper

KUSTO_TEST_URI = "https://thisclusterdoesnotexist.kusto.windows.net"
TEST_INTERACTIVE_AUTH = False  # User interaction required, enable this when running test manually

CloudSettings._cloud_cache[KUSTO_TEST_URI] = CloudSettings.DEFAULT_CLOUD
CloudSettings._cloud_cache["https://somecluster.kusto.windows.net"] = CloudSettings.DEFAULT_CLOUD


def test_unauthorized_exception():
    """Test the exception thrown when authorization fails."""
    cluster = "https://somecluster.kusto.windows.net"
    username = "username@microsoft.com"
    kcsb = KustoConnectionStringBuilder.with_aad_user_password_authentication(cluster, username, "StrongestPasswordEver", "authorityName")
    aad_helper = _AadHelper(kcsb, False)
    aad_helper.token_provider._init_resources()

    try:
        aad_helper.acquire_authorization_header()
    except KustoAuthenticationError as error:
        assert error.authentication_method == UserPassTokenProvider.name()
        assert error.authority == "https://login.microsoftonline.com/authorityName"
        assert error.kusto_cluster == cluster
        assert error.kwargs["username"] == username
        assert error.kwargs["client_id"] == CloudSettings.DEFAULT_CLOUD.kusto_client_app_id


# TODO: remove this once we can control the timeout
@pytest.mark.skip()
def test_msi_auth():
    """
    * * * Note * * *
    Each connection test takes about 15-20 seconds which is the time it takes TCP to fail connecting to the nonexistent MSI endpoint
    The timeout option does not seem to affect this behavior. Could be it only affects the waiting time fora response in successful connections.
    Please be prudent in adding any future tests!
    """
    client_guid = "kjhjk"
    object_guid = "87687687"
    res_guid = "kajsdghdijewhag"

    """
    Use of object_id and msi_res_id is disabled pending support of azure-identity
    When version 1.4.1 is released and these parameters are supported enable the functionality and tests back 
    """
    kcsb = [
        KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KUSTO_TEST_URI, timeout=1),
        KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KUSTO_TEST_URI, client_id=client_guid, timeout=1),
        # KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KUSTO_TEST_URI, object_id=object_guid, timeout=1),
        # KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(KUSTO_TEST_URI, msi_res_id=res_guid, timeout=1),
    ]

    helpers = [_AadHelper(i, False) for i in kcsb]

    for h in helpers:
        h.token_provider._init_resources()

    try:
        helpers[0].acquire_authorization_header()
    except KustoAuthenticationError as e:
        assert e.authentication_method == MsiTokenProvider.name()
        assert "client_id" not in e.kwargs
        assert "object_id" not in e.kwargs
        assert "msi_res_id" not in e.kwargs

    try:
        helpers[1].acquire_authorization_header()
    except KustoAuthenticationError as e:
        assert e.authentication_method == MsiTokenProvider.name()
        assert e.kwargs["client_id"] == client_guid
        assert "object_id" not in e.kwargs
        assert "msi_res_id" not in e.kwargs
        assert str(e.exception).index("client_id") > -1
        assert str(e.exception).index(client_guid) > -1


def test_token_provider_auth():
    valid_token_provider = lambda: "caller token"
    invalid_token_provider = lambda: 12345678

    valid_kcsb = KustoConnectionStringBuilder.with_token_provider(KUSTO_TEST_URI, valid_token_provider)
    invalid_kcsb = KustoConnectionStringBuilder.with_token_provider(KUSTO_TEST_URI, invalid_token_provider)

    valid_helper = _AadHelper(valid_kcsb, False)
    valid_helper.token_provider._init_resources()
    invalid_helper = _AadHelper(invalid_kcsb, False)
    invalid_helper.token_provider._init_resources()

    auth_header = valid_helper.acquire_authorization_header()
    assert auth_header.index(valid_token_provider()) > -1

    try:
        invalid_helper.acquire_authorization_header()
    except KustoAuthenticationError as e:
        assert e.authentication_method == CallbackTokenProvider.name()
        assert str(e.exception).index(str(type(invalid_token_provider()))) > -1


def test_user_app_token_auth():
    token = "123456446"
    user_kcsb = KustoConnectionStringBuilder.with_aad_user_token_authentication(KUSTO_TEST_URI, token)
    app_kcsb = KustoConnectionStringBuilder.with_aad_application_token_authentication(KUSTO_TEST_URI, token)

    user_helper = _AadHelper(user_kcsb, False)
    app_helper = _AadHelper(app_kcsb, False)
    user_helper.token_provider._init_resources()
    app_helper.token_provider._init_resources()

    auth_header = user_helper.acquire_authorization_header()
    assert auth_header.index(token) > -1

    auth_header = app_helper.acquire_authorization_header()
    assert auth_header.index(token) > -1


def test_interactive_login():
    if not TEST_INTERACTIVE_AUTH:
        print(" *** Skipped interactive login Test ***")
        return

    kcsb = KustoConnectionStringBuilder.with_interactive_login(KUSTO_TEST_URI)
    aad_helper = _AadHelper(kcsb, False)

    # should prompt
    header = aad_helper.acquire_authorization_header()
    assert header is not None

    # should not prompt
    header = aad_helper.acquire_authorization_header()
    assert header is not None
