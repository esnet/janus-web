"""
Unit tests for the globus_service app.

Tests are organized into:
  1. Model tests (GlobusToken, GlobusService)
  2. CLI command builder tests (services._build_*)
  3. gcs_service module tests (mocked globus-sdk)
  4. API view tests (mocked services layer)

Run with:
    cd webapp && python manage.py test globus_service
"""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from .models import GlobusToken, GlobusService
from . import services as svc
from . import gcs_service as gcs


# ---------------------------------------------------------------------------
# 1. Model tests
# ---------------------------------------------------------------------------

class GlobusTokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_create_token(self):
        token = GlobusToken.objects.create(
            user=self.user,
            token_data=json.dumps({"access_token": "abc", "refresh_token": "xyz"}),
        )
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.get_token_data()["access_token"], "abc")

    def test_set_and_get_token_data(self):
        token = GlobusToken(user=self.user, token_data="{}")
        data = {"access_token": "tok1", "refresh_token": "ref1", "expiry": "2099-01-01T00:00:00+00:00"}
        token.set_token_data(data)
        self.assertEqual(token.get_token_data()["access_token"], "tok1")

    def test_is_expired_future(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        token = GlobusToken(user=self.user, token_data=json.dumps({
            "access_token": "tok", "expiry": future
        }))
        self.assertFalse(token.is_expired())

    def test_is_expired_past(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        token = GlobusToken(user=self.user, token_data=json.dumps({
            "access_token": "tok", "expiry": past
        }))
        self.assertTrue(token.is_expired())

    def test_is_expired_no_expiry(self):
        token = GlobusToken(user=self.user, token_data=json.dumps({"access_token": "tok"}))
        self.assertTrue(token.is_expired())


class GlobusServiceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser2", password="testpass")

    def test_create_service(self):
        service = GlobusService.objects.create(
            user=self.user,
            session_id=42,
            node_name="localhost",
            container_id="abc123",
            display_name="Test Endpoint",
        )
        self.assertEqual(service.status, GlobusService.Status.PENDING)
        self.assertEqual(service.session_id, 42)

    def test_config_data_roundtrip(self):
        service = GlobusService(user=self.user, config_data="{}")
        service.set_config_data({"endpoint": {"display_name": "Test"}})
        self.assertEqual(service.get_config_data()["endpoint"]["display_name"], "Test")

    def test_merge_config_data(self):
        service = GlobusService(user=self.user, config_data='{"a": 1}')
        service.merge_config_data({"b": 2})
        data = service.get_config_data()
        self.assertEqual(data["a"], 1)
        self.assertEqual(data["b"], 2)

    def test_to_dict(self):
        service = GlobusService.objects.create(
            user=self.user,
            session_id=1,
            node_name="node1",
            container_id="cid1",
            display_name="EP",
        )
        d = service.to_dict()
        self.assertEqual(d["session_id"], 1)
        self.assertEqual(d["node_name"], "node1")
        self.assertEqual(d["status"], "pending")
        self.assertIn("created_at", d)

    def test_status_choices(self):
        service = GlobusService.objects.create(user=self.user, session_id=1)
        service.status = GlobusService.Status.ENDPOINT_CONFIGURED
        service.save()
        service.refresh_from_db()
        self.assertEqual(service.status, "endpoint_configured")


# ---------------------------------------------------------------------------
# 2. CLI command builder tests
# ---------------------------------------------------------------------------

class EndpointSetupCmdTest(TestCase):
    def test_basic_cmd(self):
        config = {
            "display_name": "My Endpoint",
            "organization": "ESNet",
            "contact_email": "admin@es.net",
        }
        cmd = svc._build_endpoint_setup_cmd(config)
        self.assertIn("globus-connect-server endpoint setup", cmd)
        # shlex.quote only adds quotes for strings with special chars
        self.assertIn("--organization ESNet", cmd)
        self.assertIn("--contact-email admin@es.net", cmd)
        self.assertIn("--agree-to-letsencrypt-tos", cmd)
        self.assertIn("-d /work/deployment-key.json", cmd)
        self.assertIn("--always-create-project", cmd)
        self.assertIn("'My Endpoint'", cmd)  # spaces → quoted

    def test_with_project_id(self):
        config = {
            "display_name": "EP",
            "organization": "Org",
            "contact_email": "a@b.com",
            "project_id": "proj-uuid-123",
        }
        cmd = svc._build_endpoint_setup_cmd(config)
        self.assertIn("--project-id proj-uuid-123", cmd)
        self.assertNotIn("--always-create-project", cmd)

    def test_with_owner(self):
        config = {
            "display_name": "EP",
            "organization": "Org",
            "contact_email": "a@b.com",
            "owner": "user@globusid.org",
        }
        cmd = svc._build_endpoint_setup_cmd(config)
        self.assertIn("--owner user@globusid.org", cmd)

    def test_custom_deployment_key_path(self):
        config = {
            "display_name": "EP",
            "organization": "Org",
            "contact_email": "a@b.com",
            "deployment_key_path": "/custom/path/key.json",
        }
        cmd = svc._build_endpoint_setup_cmd(config)
        self.assertIn("-d /custom/path/key.json", cmd)

    def test_set_owner_appended_when_service_identity_configured(self):
        """endpoint set-owner is chained after endpoint setup when GLOBUS_SERVICE_IDENTITY is set."""
        from django.test import override_settings
        config = {
            "display_name": "EP",
            "organization": "Org",
            "contact_email": "a@b.com",
        }
        with override_settings(GLOBUS_SERVICE_IDENTITY="svc@clients.auth.globus.org"):
            cmd = svc._build_endpoint_setup_cmd(config)
        self.assertIn("&& globus-connect-server endpoint set-owner", cmd)
        self.assertIn("svc@clients.auth.globus.org", cmd)

    def test_set_owner_omitted_when_service_identity_not_configured(self):
        """endpoint set-owner is omitted when GLOBUS_SERVICE_IDENTITY is not set."""
        from django.test import override_settings
        config = {
            "display_name": "EP",
            "organization": "Org",
            "contact_email": "a@b.com",
        }
        with override_settings(GLOBUS_SERVICE_IDENTITY=""):
            cmd = svc._build_endpoint_setup_cmd(config)
        self.assertNotIn("set-owner", cmd)


class GcsLoginCmdTest(TestCase):
    def test_login_cmd(self):
        cmd = svc._build_gcs_login_cmd("endpoint-uuid-123")
        # shlex.quote: alphanumeric+hyphens → no quotes added
        self.assertEqual(cmd, "globus-connect-server login endpoint-uuid-123")

    def test_get_gcs_login_cmd_chains_set_owner_when_identity_configured(self):
        """get_gcs_login_cmd wraps chained cmd in bash -c when GLOBUS_SERVICE_IDENTITY is set."""
        from django.test import override_settings
        from globus_service.models import GlobusService
        service = GlobusService.objects.create(
            user=User.objects.create_user("logintest", password="x"),
            session_id=99,
            node_name="n",
            container_id="c",
            globus_endpoint_id="ep-uuid-abc",
        )
        with override_settings(GLOBUS_SERVICE_IDENTITY="svc@clients.auth.globus.org"):
            cmd = svc.get_gcs_login_cmd(service)
        # Must be wrapped in bash -c so Docker exec interprets && as a shell operator
        self.assertTrue(cmd.startswith('bash -c "'), f"Expected bash -c wrapper, got: {cmd}")
        self.assertIn("globus-connect-server login", cmd)
        self.assertIn("ep-uuid-abc", cmd)
        self.assertIn("&&", cmd)
        self.assertIn("set-owner", cmd)
        self.assertIn("svc@clients.auth.globus.org", cmd)
        # --use-explicit-host 127.0.0.1 required so the CLI doesn't try to
        # resolve the public GCS hostname from inside the node container
        self.assertIn("--use-explicit-host", cmd)
        self.assertIn("127.0.0.1", cmd)

    def test_get_gcs_login_cmd_no_set_owner_when_identity_not_configured(self):
        """get_gcs_login_cmd returns only login cmd when GLOBUS_SERVICE_IDENTITY is empty."""
        from django.test import override_settings
        from globus_service.models import GlobusService
        service = GlobusService.objects.create(
            user=User.objects.create_user("logintest2", password="x"),
            session_id=98,
            node_name="n",
            container_id="c",
            globus_endpoint_id="ep-uuid-def",
        )
        with override_settings(GLOBUS_SERVICE_IDENTITY=""):
            cmd = svc.get_gcs_login_cmd(service)
        self.assertIn("globus-connect-server login", cmd)
        self.assertIn("ep-uuid-def", cmd)
        self.assertNotIn("set-owner", cmd)


class SetOwnerCmdTest(TestCase):
    def test_set_owner_cmd(self):
        cmd = svc._build_endpoint_set_owner_cmd("svc-acct@clients.auth.globus.org")
        self.assertIn("endpoint set-owner", cmd)
        self.assertIn("svc-acct@clients.auth.globus.org", cmd)


class StorageGatewayCmdTest(TestCase):
    def test_basic_posix_gateway(self):
        config = {
            "connector": "posix",
            "display_name": "BNL DTNAAS Gateway",
            "gateway_name": "bnl-gateway",  # gateway_name is NOT a positional arg
            "domain": "es.net",
            "user_deny": "root",
        }
        cmd = svc._build_storage_gateway_cmd(config)
        self.assertIn("storage-gateway create posix", cmd)
        self.assertIn("'BNL DTNAAS Gateway'", cmd)   # spaces → quoted
        self.assertIn("--domain es.net", cmd)          # no special chars → no quotes
        self.assertIn("--user-deny root", cmd)
        # gateway_name is NOT appended as a positional arg (GCS CLI doesn't support it)
        self.assertNotIn("bnl-gateway", cmd)

    def test_restrict_paths_file(self):
        config = {
            "connector": "posix",
            "display_name": "GW",
            "gateway_name": "gw",
            "restrict_paths_file": "/work/path-restrictions.json",
        }
        cmd = svc._build_storage_gateway_cmd(config)
        self.assertIn("--restrict-paths file:/work/path-restrictions.json", cmd)

    def test_restrict_paths_inline(self):
        config = {
            "connector": "posix",
            "display_name": "GW",
            "gateway_name": "gw",
            "restrict_paths_file": "",
            "restrict_paths": ["/data/shared", "/data/public"],
        }
        cmd = svc._build_storage_gateway_cmd(config)
        # shlex.quote adds quotes for paths (contain /)
        self.assertIn("--restrict-paths /data/shared", cmd)
        self.assertIn("--restrict-paths /data/public", cmd)

    def test_multiple_user_deny(self):
        config = {
            "connector": "posix",
            "display_name": "GW",
            "gateway_name": "gw",
            "user_deny": "root,nobody",
        }
        cmd = svc._build_storage_gateway_cmd(config)
        self.assertIn("--user-deny root", cmd)
        self.assertIn("--user-deny nobody", cmd)


class CollectionCreateCmdTest(TestCase):
    def test_basic_collection(self):
        config = {
            "storage_gateway_id": "gw-uuid-123",
            "base_path": "/data/ESnet/",
            "display_name": "ESnet read-only Collection at BNL DTNAAS",
        }
        cmd = svc._build_collection_create_cmd(config)
        self.assertIn("collection create", cmd)
        # shlex.quote: alphanumeric+hyphens → no quotes; paths → no quotes
        self.assertIn("gw-uuid-123", cmd)
        self.assertIn("/data/ESnet/", cmd)
        self.assertIn("'ESnet read-only Collection at BNL DTNAAS'", cmd)  # spaces → quoted

    def test_with_description_and_keywords(self):
        config = {
            "storage_gateway_id": "gw-uuid",
            "base_path": "/data/",
            "display_name": "My Collection",
            "description": "Test collection",
            "keywords": "testing,dtn",
        }
        cmd = svc._build_collection_create_cmd(config)
        self.assertIn("--description 'Test collection'", cmd)   # spaces → quoted
        self.assertIn("--keywords testing,dtn", cmd)             # comma but no spaces → no quotes

    def test_enable_anonymous_writes(self):
        config = {
            "storage_gateway_id": "gw-uuid",
            "base_path": "/data/write/",
            "display_name": "RW Collection",
            "enable_anonymous_writes": True,
        }
        cmd = svc._build_collection_create_cmd(config)
        self.assertIn("--enable-anonymous-writes", cmd)

    def test_sharing_restrict_paths_file(self):
        config = {
            "storage_gateway_id": "gw-uuid",
            "base_path": "/data/",
            "display_name": "RO Collection",
            "sharing_restrict_paths_file": "/work/sharing-restrictions.json",
        }
        cmd = svc._build_collection_create_cmd(config)
        self.assertIn("--sharing-restrict-paths file:/work/sharing-restrictions.json", cmd)

    def test_no_anonymous_writes_by_default(self):
        config = {
            "storage_gateway_id": "gw-uuid",
            "base_path": "/data/",
            "display_name": "Collection",
        }
        cmd = svc._build_collection_create_cmd(config)
        self.assertNotIn("--enable-anonymous-writes", cmd)


# ---------------------------------------------------------------------------
# 3. Services layer tests (mocked exec)
# ---------------------------------------------------------------------------

class ServicesTokenTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tokuser", password="pass")

    def test_store_and_retrieve_tokens(self):
        data = {"access_token": "at1", "refresh_token": "rt1", "expiry": "2099-01-01T00:00:00+00:00"}
        svc.store_tokens(self.user, data)
        token = GlobusToken.objects.get(user=self.user)
        self.assertEqual(token.get_token_data()["access_token"], "at1")

    def test_get_valid_access_token_not_expired(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        svc.store_tokens(self.user, {"access_token": "valid_tok", "expiry": future})
        tok = svc.get_valid_access_token(self.user)
        self.assertEqual(tok, "valid_tok")

    def test_get_valid_access_token_no_token(self):
        tok = svc.get_valid_access_token(self.user)
        self.assertIsNone(tok)

    def test_has_valid_tokens_false(self):
        self.assertFalse(svc.has_valid_tokens(self.user))

    def test_has_valid_tokens_true(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        svc.store_tokens(self.user, {"access_token": "tok", "expiry": future})
        self.assertTrue(svc.has_valid_tokens(self.user))

    def test_delete_tokens(self):
        svc.store_tokens(self.user, {"access_token": "tok"})
        svc.delete_tokens(self.user)
        self.assertFalse(GlobusToken.objects.filter(user=self.user).exists())

    @patch("globus_service.gcs_service.refresh_tokens")
    def test_get_valid_access_token_refreshes_expired(self, mock_refresh):
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        svc.store_tokens(self.user, {
            "access_token": "old_tok",
            "refresh_token": "ref_tok",
            "expiry": past,
        })
        mock_refresh.return_value = {"access_token": "new_tok", "expiry": future}
        with patch("globus_service.services._get_globus_client_id", return_value="client-id"):
            tok = svc.get_valid_access_token(self.user)
        self.assertEqual(tok, "new_tok")


class ServicesCRUDTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cruduser", password="pass")

    def test_create_service(self):
        service = svc.create_service(self.user, 10, "node1", "cid1", "My EP")
        self.assertEqual(service.session_id, 10)
        self.assertEqual(service.status, GlobusService.Status.PENDING)

    def test_get_service(self):
        created = svc.create_service(self.user, 10, "node1", "cid1")
        fetched = svc.get_service(created.pk, self.user)
        self.assertEqual(fetched.pk, created.pk)

    def test_get_service_wrong_user(self):
        other = User.objects.create_user(username="other", password="pass")
        created = svc.create_service(self.user, 10, "node1", "cid1")
        fetched = svc.get_service(created.pk, other)
        self.assertIsNone(fetched)

    def test_list_services(self):
        svc.create_service(self.user, 1, "n1", "c1")
        svc.create_service(self.user, 2, "n2", "c2")
        services = svc.list_services(self.user)
        self.assertEqual(len(services), 2)

    def test_delete_service(self):
        created = svc.create_service(self.user, 10, "node1", "cid1")
        result = svc.delete_service(created.pk, self.user)
        self.assertTrue(result)
        self.assertFalse(GlobusService.objects.filter(pk=created.pk).exists())

    def test_delete_service_not_found(self):
        result = svc.delete_service(99999, self.user)
        self.assertFalse(result)


class ServicesExecTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="execuser", password="pass")
        self.service = svc.create_service(self.user, 1, "localhost", "cid123")

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_exec_in_container_success(self, mock_post, mock_ws_create):
        """
        _exec_in_container now:
          1. POSTs to /exec → gets {"Id": "exec-id"}
          2. Opens WebSocket → streams output
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Id": "exec-id-123", "node_id": 11}
        mock_post.return_value = mock_resp

        mock_ws = MagicMock()
        # recv() returns output then raises to end the loop
        mock_ws.recv.side_effect = ["hello world\n", Exception("stream closed")]
        mock_ws_create.return_value = mock_ws

        success, output = svc._exec_in_container("localhost", "cid123", "echo hello")
        self.assertTrue(success)
        self.assertIn("hello world", output)

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_exec_in_container_failure(self, mock_post, mock_ws_create):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "container not found"}
        mock_post.return_value = mock_resp

        success, output = svc._exec_in_container("localhost", "cid123", "echo hello")
        self.assertFalse(success)

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_fetch_deployment_key(self, mock_post, mock_ws_create):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Id": "exec-id-456", "node_id": 11}
        mock_post.return_value = mock_resp

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = ['{"node_key": {"kty": "RSA"}}', Exception("done")]
        mock_ws_create.return_value = mock_ws

        success, output = svc.fetch_deployment_key(self.service)
        self.assertTrue(success)
        self.assertIn("node_key", output)
        self.service.refresh_from_db()
        self.assertIn("deployment_key", self.service.get_config_data())
        self.assertEqual(self.service.status, GlobusService.Status.ENDPOINT_CONFIGURED)

    def test_get_gcs_login_cmd_no_endpoint_id(self):
        with self.assertRaises(ValueError):
            svc.get_gcs_login_cmd(self.service)

    def test_get_gcs_login_cmd_with_endpoint_id(self):
        self.service.globus_endpoint_id = "ep-uuid-123"
        self.service.save()
        cmd = svc.get_gcs_login_cmd(self.service)
        self.assertIn("globus-connect-server login", cmd)
        self.assertIn("ep-uuid-123", cmd)

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_run_storage_gateway_create(self, mock_post, mock_ws_create):
        """Legacy CLI-based gateway create still works (kept for backward compat)."""
        self.service.status = GlobusService.Status.NODE_CONFIGURED
        self.service.save()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Id": "exec-gw-123", "node_id": 11}
        mock_post.return_value = mock_resp

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = [
            "Created storage gateway abc12345-1234-1234-1234-abcdef123456",
            Exception("done"),
        ]
        mock_ws_create.return_value = mock_ws

        config = {
            "connector": "posix",
            "display_name": "Test GW",
            "gateway_name": "test-gw",
        }
        success, output = svc.run_storage_gateway_create(self.service, config)
        self.assertTrue(success)
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, GlobusService.Status.GATEWAY_CONFIGURED)

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_run_collection_create(self, mock_post, mock_ws_create):
        """Legacy CLI-based collection create still works (kept for backward compat)."""
        self.service.status = GlobusService.Status.GATEWAY_CONFIGURED
        self.service.save()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Id": "exec-col-123", "node_id": 11}
        mock_post.return_value = mock_resp

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = [
            "Created collection col12345-1234-1234-1234-abcdef123456",
            Exception("done"),
        ]
        mock_ws_create.return_value = mock_ws

        config = {
            "storage_gateway_id": "gw-uuid",
            "base_path": "/data/ESnet/",
            "display_name": "Test Collection",
        }
        success, output = svc.run_collection_create(self.service, config)
        self.assertTrue(success)
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, GlobusService.Status.COLLECTIONS_CONFIGURED)

    def test_run_node_setup_no_cmd(self):
        """run_node_setup no longer calls _build_node_setup_cmd — just transitions status."""
        config = {"ip_address": "10.0.0.1"}
        success, output = svc.run_node_setup(self.service, config)
        self.assertTrue(success)
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, GlobusService.Status.NODE_CONFIGURED)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    def test_create_gateway_via_api(self, mock_get_client):
        """create_gateway_via_api uses service account REST API."""
        self.service.globus_endpoint_id = "ep-uuid-abc"
        self.service.set_config_data({"gcs_address": "ep-uuid-abc.data.globus.org"})
        self.service.save()

        mock_client = MagicMock()
        mock_client.create_storage_gateway.return_value = MagicMock(data={"id": "gw-api-uuid-123"})
        mock_get_client.return_value = mock_client

        config = {"connector": "posix", "display_name": "API Gateway"}
        success, output = svc.create_gateway_via_api(self.service, config)
        self.assertTrue(success)
        self.assertEqual(output, "gw-api-uuid-123")
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, GlobusService.Status.GATEWAY_CONFIGURED)

    def test_create_gateway_via_api_no_endpoint(self):
        """create_gateway_via_api fails gracefully when endpoint_id is missing."""
        config = {"connector": "posix", "display_name": "API Gateway"}
        success, output = svc.create_gateway_via_api(self.service, config)
        self.assertFalse(success)
        self.assertIn("endpoint_id", output)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    def test_create_collection_via_api_mapped(self, mock_get_client):
        """create_collection_via_api creates a mapped collection via REST API."""
        self.service.globus_endpoint_id = "ep-uuid-abc"
        self.service.set_config_data({
            "gcs_address": "ep-uuid-abc.data.globus.org",
            "storage_gateway": {"id": "gw-uuid-123"},
        })
        self.service.save()

        mock_client = MagicMock()
        mock_client.create_collection.return_value = MagicMock(data={"id": "col-api-uuid-456"})
        mock_get_client.return_value = mock_client

        config = {
            "base_path": "/data/",
            "display_name": "API Collection",
            "collection_type": "mapped",
            # Gap 1
            "organization": "ESnet",
            # Gap 2
            "keywords": "testing, dtn",
            # Gap 3
            "sharing_rw": "/work",
            "sharing_ro": "/data/shared",
            "sharing_none": "",
            # Gap 4
            "disable_anonymous_writes": True,
            "allow_guest_collections": False,
        }
        success, output = svc.create_collection_via_api(self.service, config)
        self.assertTrue(success)
        self.assertEqual(output, "col-api-uuid-456")
        self.service.refresh_from_db()
        self.assertEqual(self.service.status, GlobusService.Status.COLLECTIONS_CONFIGURED)

        # Verify MappedCollectionDocument received the correct assembled fields
        call_doc = mock_client.create_collection.call_args[0][0]
        self.assertEqual(call_doc["organization"], "ESnet")
        self.assertEqual(call_doc["keywords"], ["testing", "dtn"])
        self.assertTrue(call_doc["disable_anonymous_writes"])
        self.assertFalse(call_doc["allow_guest_collections"])
        srp = call_doc["sharing_restrict_paths"]
        self.assertEqual(srp["DATA_TYPE"], "path_restrictions#1.0.0")
        self.assertEqual(srp["read_write"], ["/work"])
        self.assertEqual(srp["read"], ["/data/shared"])
        self.assertEqual(srp["none"], [])

    def test_derive_gcs_address(self):
        """derive_gcs_address returns <endpoint_id>.data.globus.org."""
        addr = svc.derive_gcs_address("abc123")
        self.assertEqual(addr, "abc123.data.globus.org")


# ---------------------------------------------------------------------------
# 4. API view tests
# ---------------------------------------------------------------------------

class GlobusServiceAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="apiuser", password="apipass")
        self.client.login(username="apiuser", password="apipass")

    def test_list_services_empty(self):
        resp = self.client.get("/janus/services/api/globus/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["services"], [])

    def test_list_services_unauthenticated(self):
        self.client.logout()
        resp = self.client.get("/janus/services/api/globus/")
        self.assertEqual(resp.status_code, 401)

    def test_create_service(self):
        resp = self.client.post(
            "/janus/services/api/globus/create/",
            data=json.dumps({"session_id": 5, "node_name": "node1", "container_id": "cid1"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["service"]["session_id"], 5)
        self.assertEqual(data["service"]["status"], "pending")

    def test_create_service_missing_session_id(self):
        resp = self.client.post(
            "/janus/services/api/globus/create/",
            data=json.dumps({"node_name": "node1"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_service(self):
        service = svc.create_service(self.user, 1, "n1", "c1", "EP")
        resp = self.client.get(f"/janus/services/api/globus/{service.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["service"]["id"], service.pk)

    def test_get_service_not_found(self):
        resp = self.client.get("/janus/services/api/globus/99999/")
        self.assertEqual(resp.status_code, 404)

    def test_delete_service(self):
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(f"/janus/services/api/globus/{service.pk}/delete/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(GlobusService.objects.filter(pk=service.pk).exists())

    def test_auth_status_no_tokens(self):
        resp = self.client.get("/janus/services/api/globus/auth/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["authenticated"])

    def test_auth_status_with_tokens(self):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        svc.store_tokens(self.user, {"access_token": "tok", "expiry": future})
        resp = self.client.get("/janus/services/api/globus/auth/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["authenticated"])

    def test_auth_logout(self):
        svc.store_tokens(self.user, {"access_token": "tok"})
        resp = self.client.post("/janus/services/api/globus/auth/logout/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(GlobusToken.objects.filter(user=self.user).exists())

    @patch("globus_service.services.build_auth_url")
    def test_get_auth_url(self, mock_build):
        # build_auth_url now returns (auth_url, state, pkce_data)
        mock_build.return_value = (
            "https://auth.globus.org/v2/oauth2/authorize?...",
            "state123",
            {"verifier": "test-verifier-43-chars-long-padding-here"},
        )
        resp = self.client.get("/janus/services/api/globus/auth/url/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("auth_url", data)
        self.assertIn("state", data)

    @patch("globus_service.services.build_auth_url")
    def test_get_auth_url_no_client_id(self, mock_build):
        mock_build.side_effect = RuntimeError("GLOBUS_CLIENT_ID is not configured")
        resp = self.client.get("/janus/services/api/globus/auth/url/")
        self.assertEqual(resp.status_code, 500)

    @patch("globus_service.services.ws_lib.create_connection")
    @patch("globus_service.services.httpx.post")
    def test_exec_command(self, mock_post, mock_ws_create):
        service = svc.create_service(self.user, 1, "n1", "c1")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Id": "exec-id-test", "node_id": 11}
        mock_post.return_value = mock_resp

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = ["command output\n", Exception("done")]
        mock_ws_create.return_value = mock_ws

        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/exec/",
            data=json.dumps({"cmd": "echo hello"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("output", resp.json())

    def test_exec_command_empty_cmd(self):
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/exec/",
            data=json.dumps({"cmd": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_endpoint_setup_cmd(self):
        service = svc.create_service(self.user, 1, "n1", "c1", "My EP")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/cmd/",
            data=json.dumps({
                "display_name": "My EP",
                "organization": "ESNet",
                "contact_email": "admin@es.net",
                "owner": "user@globusid.org",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cmd", data)
        self.assertIn("globus-connect-server endpoint setup", data["cmd"])
        self.assertIn("--agree-to-letsencrypt-tos", data["cmd"])
        self.assertIn("--owner user@globusid.org", data["cmd"])

    def test_get_endpoint_setup_cmd_missing_fields(self):
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/cmd/",
            data=json.dumps({"display_name": "EP", "organization": "Org", "contact_email": "a@b.com"}),
            content_type="application/json",
        )
        # Missing owner → 400
        self.assertEqual(resp.status_code, 400)

    def test_get_gcs_login_cmd_api(self):
        """GET /node/login-cmd/ returns cmd containing gcs login for a service with endpoint_id."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        service.globus_endpoint_id = "ep-uuid-view-test"
        service.save()
        resp = self.client.get(
            f"/janus/services/api/globus/{service.pk}/node/login-cmd/",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cmd", data)
        self.assertIn("globus-connect-server login", data["cmd"])
        self.assertIn("ep-uuid-view-test", data["cmd"])

    def test_get_gcs_login_cmd_api_no_endpoint_id(self):
        """GET /node/login-cmd/ returns 400 when service has no endpoint_id."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.get(
            f"/janus/services/api/globus/{service.pk}/node/login-cmd/",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_set_endpoint_owner(self):
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/set-owner/",
            data=json.dumps({"service_account_id": "svc@clients.auth.globus.org"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cmd", data)
        self.assertIn("endpoint set-owner", data["cmd"])

    def test_set_endpoint_owner_missing_id(self):
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/set-owner/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("globus_service.services.create_gateway_via_api")
    def test_setup_gateway(self, mock_create_gw):
        """create_gateway_api now calls create_gateway_via_api (service account REST)."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        mock_create_gw.return_value = (True, "gw-api-uuid-123")

        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/gateway/create/",
            data=json.dumps({
                "connector": "posix",
                "display_name": "Test GW",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(resp.json()["gateway_id"], "gw-api-uuid-123")

    def test_setup_gateway_missing_fields(self):
        """create_gateway_api requires connector and display_name."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/gateway/create/",
            data=json.dumps({"connector": "posix"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("globus_service.services.create_collection_via_api")
    def test_create_collection(self, mock_create_col):
        """create_collection_api now calls create_collection_via_api (service account REST)."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        mock_create_col.return_value = (True, "col-api-uuid-456")

        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/collection/create/",
            data=json.dumps({
                "base_path": "/data/ESnet/",
                "display_name": "Test Collection",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(resp.json()["collection_id"], "col-api-uuid-456")

    def test_create_collection_missing_fields(self):
        """create_collection_api requires base_path and display_name."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/collection/create/",
            data=json.dumps({"display_name": "Test"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    def test_list_gateways_api(self, mock_get_client):
        """list_gateways_api returns gateway list from GCS REST API."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        service.globus_endpoint_id = "ep-uuid-list"
        service.set_config_data({"gcs_address": "ep-uuid-list.data.globus.org"})
        service.save()

        mock_client = MagicMock()
        mock_client.get_storage_gateway_list.return_value = [{"id": "gw1"}, {"id": "gw2"}]
        mock_get_client.return_value = mock_client

        resp = self.client.get(f"/janus/services/api/globus/{service.pk}/gateway/list/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("gateways", data)

    def test_list_gateways_api_no_endpoint(self):
        """list_gateways_api returns 400 when endpoint_id is not set."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.get(f"/janus/services/api/globus/{service.pk}/gateway/list/")
        self.assertEqual(resp.status_code, 400)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    def test_list_collections_api(self, mock_get_client):
        """list_collections_api returns collection list from GCS REST API."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        service.globus_endpoint_id = "ep-uuid-list"
        service.set_config_data({"gcs_address": "ep-uuid-list.data.globus.org"})
        service.save()

        mock_client = MagicMock()
        mock_client.get_collection_list.return_value = [{"id": "col1"}]
        mock_get_client.return_value = mock_client

        resp = self.client.get(f"/janus/services/api/globus/{service.pk}/collection/list/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("collections", data)

    def test_list_collections_api_no_endpoint(self):
        """list_collections_api returns 400 when endpoint_id is not set."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.get(f"/janus/services/api/globus/{service.pk}/collection/list/")
        self.assertEqual(resp.status_code, 400)

    @patch("globus_service.services.grant_user_admin_role")
    def test_grant_user_admin_api_with_identity_id(self, mock_grant):
        """POST endpoint/grant-admin/ with identity_id calls grant_user_admin_role."""
        mock_grant.return_value = (True, "Administrator role granted to test-identity-uuid.")
        service = svc.create_service(self.user, 1, "n1", "c1")
        service.globus_endpoint_id = "ep-uuid"
        service.save()
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/grant-admin/",
            data=json.dumps({"identity_id": "test-identity-uuid"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identity_id"], "test-identity-uuid")
        mock_grant.assert_called_once_with(service, "test-identity-uuid")

    @patch("globus_service.gcs_service.get_globus_identity_id")
    @patch("globus_service.services.grant_user_admin_role")
    def test_grant_user_admin_api_with_username(self, mock_grant, mock_lookup):
        """POST endpoint/grant-admin/ with username looks up identity then grants role."""
        mock_lookup.return_value = "looked-up-uuid"
        mock_grant.return_value = (True, "Administrator role granted to looked-up-uuid.")
        service = svc.create_service(self.user, 1, "n1", "c1")
        service.globus_endpoint_id = "ep-uuid"
        service.save()
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/grant-admin/",
            data=json.dumps({"username": "user@globusid.org"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["identity_id"], "looked-up-uuid")
        mock_lookup.assert_called_once_with("user@globusid.org")
        mock_grant.assert_called_once_with(service, "looked-up-uuid")

    @patch("globus_service.gcs_service.get_globus_identity_id")
    def test_grant_user_admin_api_username_not_found(self, mock_lookup):
        """POST endpoint/grant-admin/ returns 404 when username has no Globus identity."""
        mock_lookup.return_value = None
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/grant-admin/",
            data=json.dumps({"username": "nobody@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_grant_user_admin_api_missing_fields(self):
        """POST endpoint/grant-admin/ without identity_id or username returns 400."""
        service = svc.create_service(self.user, 1, "n1", "c1")
        resp = self.client.post(
            f"/janus/services/api/globus/{service.pk}/endpoint/grant-admin/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 5. gcs_service module tests (mocked globus-sdk)
# ---------------------------------------------------------------------------

class GcsServiceTest(TestCase):
    def test_derive_gcs_address(self):
        """derive_gcs_address returns <endpoint_id>.data.globus.org."""
        addr = gcs.derive_gcs_address("abc123-uuid")
        self.assertEqual(addr, "abc123-uuid.data.globus.org")

    @patch("globus_sdk.ConfidentialAppAuthClient")
    @patch("globus_sdk.ClientCredentialsAuthorizer")
    @patch("globus_sdk.GCSClient")
    def test_get_gcs_client_service_account(self, mock_gcs_cls, mock_auth_cls, mock_conf_cls):
        """get_gcs_client_service_account builds a GCSClient with ClientCredentialsAuthorizer."""
        from django.test import override_settings
        with override_settings(
            GLOBUS_SERVICE_CLIENT_ID="test-client-id",
            GLOBUS_SERVICE_CLIENT_SECRET="test-secret",
        ):
            mock_conf_client = MagicMock()
            mock_conf_cls.return_value = mock_conf_client
            mock_authorizer = MagicMock()
            mock_auth_cls.return_value = mock_authorizer
            mock_gcs_instance = MagicMock()
            mock_gcs_cls.return_value = mock_gcs_instance

            client = gcs.get_gcs_client_service_account(
                "ep-uuid.data.globus.org", "ep-uuid"
            )
            mock_conf_cls.assert_called_once_with("test-client-id", "test-secret")
            mock_auth_cls.assert_called_once()
            mock_gcs_cls.assert_called_once()
            self.assertEqual(client, mock_gcs_instance)

    def test_get_gcs_client_service_account_missing_settings(self):
        """get_gcs_client_service_account raises RuntimeError when credentials missing."""
        from django.test import override_settings
        with override_settings(GLOBUS_SERVICE_CLIENT_ID="", GLOBUS_SERVICE_CLIENT_SECRET=""):
            with self.assertRaises(RuntimeError):
                gcs.get_gcs_client_service_account("ep.data.globus.org", "ep-uuid")

    @patch("globus_service.gcs_service._get_native_client")
    def test_get_auth_url(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.oauth2_get_authorize_url.return_value = "https://auth.globus.org/authorize?..."
        # Mock the flow manager to return a verifier
        mock_flow = MagicMock()
        mock_flow.verifier = "test-verifier-43-chars-long-padding-here-xx"
        mock_client.current_oauth2_flow_manager = mock_flow
        mock_client_factory.return_value = mock_client

        # get_auth_url now returns (url, verifier) tuple
        url, verifier = gcs.get_auth_url("client-id", "https://example.com/callback", "state123")
        self.assertIn("https://auth.globus.org", url)
        self.assertIsNotNone(verifier)
        mock_client.oauth2_start_flow.assert_called_once()

    @patch("globus_service.gcs_service._get_native_client")
    def test_exchange_code_for_tokens(self, mock_client_factory):
        mock_client = MagicMock()
        mock_token_resp = MagicMock()
        mock_token_resp.by_resource_server = {
            "transfer.api.globus.org": {
                "access_token": "at123",
                "refresh_token": "rt123",
                "expires_in": 3600,
                "scope": "urn:globus:auth:scope:transfer.api.globus.org:all",
            }
        }
        mock_client.oauth2_exchange_code_for_tokens.return_value = mock_token_resp
        mock_client_factory.return_value = mock_client

        result = gcs.exchange_code_for_tokens("client-id", "https://example.com/cb", "auth-code")
        self.assertEqual(result["access_token"], "at123")
        self.assertEqual(result["refresh_token"], "rt123")
        self.assertIn("expiry", result)

    def test_get_connector_id_posix(self):
        connector_id = gcs.get_connector_id("posix")
        self.assertIsNotNone(connector_id)
        # Should be a UUID-like string
        self.assertRegex(connector_id, r"[0-9a-f-]{36}")

    def test_get_connector_id_unknown(self):
        connector_id = gcs.get_connector_id("nonexistent-connector")
        self.assertIsNone(connector_id)

    @patch("globus_sdk.ConfidentialAppAuthClient")
    def test_get_globus_identity_id_found(self, mock_conf_cls):
        """get_globus_identity_id returns UUID when identity exists."""
        from django.test import override_settings
        mock_client = MagicMock()
        mock_conf_cls.return_value = mock_client
        mock_client.get_identities.return_value = MagicMock(
            data={"identities": [{"id": "found-uuid-1234"}]}
        )
        with override_settings(
            GLOBUS_SERVICE_CLIENT_ID="test-id",
            GLOBUS_SERVICE_CLIENT_SECRET="test-secret",
        ):
            result = gcs.get_globus_identity_id("user@globusid.org")
        self.assertEqual(result, "found-uuid-1234")
        mock_client.get_identities.assert_called_once_with(usernames=["user@globusid.org"])

    @patch("globus_sdk.ConfidentialAppAuthClient")
    def test_get_globus_identity_id_not_found(self, mock_conf_cls):
        """get_globus_identity_id returns None when no identity matches."""
        from django.test import override_settings
        mock_client = MagicMock()
        mock_conf_cls.return_value = mock_client
        mock_client.get_identities.return_value = MagicMock(data={"identities": []})
        with override_settings(
            GLOBUS_SERVICE_CLIENT_ID="test-id",
            GLOBUS_SERVICE_CLIENT_SECRET="test-secret",
        ):
            result = gcs.get_globus_identity_id("nobody@example.com")
        self.assertIsNone(result)

    def test_get_globus_identity_id_missing_settings(self):
        """get_globus_identity_id raises RuntimeError when credentials not configured."""
        from django.test import override_settings
        with override_settings(GLOBUS_SERVICE_CLIENT_ID="", GLOBUS_SERVICE_CLIENT_SECRET=""):
            with self.assertRaises(RuntimeError):
                gcs.get_globus_identity_id("user@globusid.org")

    @patch("httpx.put")
    def test_set_endpoint_owner_via_api(self, mock_put):
        """set_endpoint_owner_via_api PUTs to the correct URL with bearer token."""
        mock_resp = MagicMock()
        mock_resp.content = b'{"result": "ok"}'
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()
        mock_put.return_value = mock_resp

        result = gcs.set_endpoint_owner_via_api(
            "ep-uuid.data.globus.org", "identity-uuid", "bearer-token-abc"
        )
        self.assertEqual(result, {"result": "ok"})
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        self.assertIn("https://ep-uuid.data.globus.org/api/endpoint/owner", call_args[0])
        self.assertEqual(
            call_args[1]["headers"]["Authorization"], "Bearer bearer-token-abc"
        )
        self.assertEqual(call_args[1]["json"]["identity_id"], "identity-uuid")

    def test_create_role(self):
        """create_role calls client.create_role with a GCSRoleDocument."""
        import globus_sdk
        mock_client = MagicMock()
        mock_client.create_role.return_value = MagicMock(data={"id": "role-uuid", "role": "administrator"})

        gcs.create_role(mock_client, "collection-uuid", "identity-uuid", "administrator")
        mock_client.create_role.assert_called_once()
        call_arg = mock_client.create_role.call_args[0][0]
        self.assertIsInstance(call_arg, globus_sdk.GCSRoleDocument)


# ---------------------------------------------------------------------------
# 6. services ownership / admin-role tests
# ---------------------------------------------------------------------------

class ServicesOwnershipTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owneruser", password="pw")
        self.service = svc.create_service(self.user, 1, "n1", "c1")
        self.service.globus_endpoint_id = "ep-uuid-own"
        self.service.set_config_data({"gcs_address": "ep-uuid-own.data.globus.org"})
        self.service.save()

    @patch("globus_service.gcs_service.set_endpoint_owner_via_api")
    @patch("globus_service.services.get_valid_access_token")
    def test_transfer_endpoint_ownership_success(self, mock_get_token, mock_set_owner):
        """transfer_endpoint_ownership uses the user's token to authorize the ownership PUT."""
        from django.test import override_settings
        mock_get_token.return_value = "user-bearer-abc"
        mock_set_owner.return_value = {}

        with override_settings(
            GLOBUS_SERVICE_CLIENT_ID="svc-client-id",
            GLOBUS_SERVICE_CLIENT_SECRET="svc-secret",
        ):
            success, msg = svc.transfer_endpoint_ownership(self.service)

        self.assertTrue(success)
        mock_get_token.assert_called_once_with(self.service.user)
        mock_set_owner.assert_called_once_with(
            "ep-uuid-own.data.globus.org", "svc-client-id", "user-bearer-abc",
            verify_tls=True, local_address="",
        )

    def test_transfer_endpoint_ownership_no_endpoint_id(self):
        """transfer_endpoint_ownership returns False when endpoint_id is missing."""
        self.service.globus_endpoint_id = ""
        self.service.set_config_data({})
        self.service.save()
        success, msg = svc.transfer_endpoint_ownership(self.service)
        self.assertFalse(success)
        self.assertIn("endpoint_id", msg)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    @patch("globus_service.gcs_service.create_role")
    def test_grant_user_admin_role_success(self, mock_create_role, mock_get_client):
        """grant_user_admin_role calls create_role with administrator role."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_create_role.return_value = {"id": "role-uuid"}

        success, msg = svc.grant_user_admin_role(self.service, "user-identity-uuid")

        self.assertTrue(success)
        mock_get_client.assert_called_once_with(
            "ep-uuid-own.data.globus.org", "ep-uuid-own", verify_tls=True, local_address=""
        )
        mock_create_role.assert_called_once_with(
            mock_client, "ep-uuid-own", "user-identity-uuid", role="administrator"
        )

    def test_grant_user_admin_role_no_endpoint_id(self):
        """grant_user_admin_role returns False when endpoint_id is missing."""
        self.service.globus_endpoint_id = ""
        self.service.set_config_data({})
        self.service.save()
        success, msg = svc.grant_user_admin_role(self.service, "user-identity-uuid")
        self.assertFalse(success)
        self.assertIn("endpoint_id", msg)

    @patch("globus_service.gcs_service.get_gcs_client_service_account")
    def test_grant_user_admin_role_exception_is_non_fatal(self, mock_get_client):
        """grant_user_admin_role returns (False, error_msg) on exception — does not raise."""
        mock_get_client.side_effect = RuntimeError("GCS unreachable")
        success, msg = svc.grant_user_admin_role(self.service, "user-identity-uuid")
        self.assertFalse(success)
        self.assertIn("GCS unreachable", msg)
