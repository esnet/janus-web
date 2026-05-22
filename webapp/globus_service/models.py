import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class GlobusToken(models.Model):
    """
    Stores Globus OAuth2 tokens for a user.
    One token set per user (unique on user).
    Tokens are stored as plain text; operators should ensure DB-level encryption
    or use an encrypted field library in production.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="globus_token",
    )
    # Serialized JSON of the full token response from globus-sdk
    token_data = models.TextField(
        help_text="JSON-serialized Globus token response (access_token, refresh_token, expiry, scopes)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Globus Token"
        verbose_name_plural = "Globus Tokens"

    def __str__(self):
        return f"GlobusToken(user={self.user.username})"

    def get_token_data(self):
        """Return deserialized token dict."""
        try:
            return json.loads(self.token_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_token_data(self, data: dict):
        """Serialize and store token dict."""
        self.token_data = json.dumps(data)

    def is_expired(self):
        """Return True if the access token has expired."""
        data = self.get_token_data()
        expiry_str = data.get("expiry")
        if not expiry_str:
            return True
        try:
            from datetime import datetime
            expiry = datetime.fromisoformat(expiry_str)
            if expiry.tzinfo is None:
                expiry = timezone.make_aware(expiry)
            return timezone.now() >= expiry
        except Exception:
            return True


class GlobusService(models.Model):
    """
    Tracks the lifecycle of a GCS v5 endpoint configuration for a user.
    Each record corresponds to one GCS endpoint being set up inside a
    Janus session container.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTH_COMPLETE = "auth_complete", "Auth Complete"
        ENDPOINT_CONFIGURED = "endpoint_configured", "Endpoint Configured"
        NODE_CONFIGURED = "node_configured", "Node Configured"
        GATEWAY_CONFIGURED = "gateway_configured", "Gateway Configured"
        COLLECTIONS_CONFIGURED = "collections_configured", "Collections Configured"
        COMPLETE = "complete", "Complete"
        ERROR = "error", "Error"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="globus_services",
    )
    # Janus session ID (integer ID from the Janus Controller)
    session_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Janus Controller session ID hosting the GCS container",
    )
    # Node name within the session (key in the services dict)
    node_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Janus node name where the GCS container is running",
    )
    # Docker container ID on the node
    container_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Container ID of the GCS container",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Globus endpoint UUID assigned after endpoint setup
    globus_endpoint_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Globus endpoint UUID (populated after endpoint setup)",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-readable display name for the GCS endpoint",
    )
    # JSON blob storing the full configuration submitted at each wizard step
    config_data = models.TextField(
        blank=True,
        default="{}",
        help_text="JSON-serialized configuration data collected across wizard steps",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Last error message if status=error",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Globus Service"
        verbose_name_plural = "Globus Services"
        ordering = ["-created_at"]

    def __str__(self):
        return f"GlobusService(id={self.pk}, user={self.user.username}, status={self.status})"

    def get_config_data(self) -> dict:
        """Return deserialized config dict."""
        try:
            return json.loads(self.config_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config_data(self, data: dict):
        """Serialize and store config dict."""
        self.config_data = json.dumps(data)

    def merge_config_data(self, new_data: dict):
        """Merge new_data into existing config and save."""
        existing = self.get_config_data()
        existing.update(new_data)
        self.set_config_data(existing)

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation for API responses."""
        return {
            "id": self.pk,
            "user": self.user.username,
            "session_id": self.session_id,
            "node_name": self.node_name,
            "container_id": self.container_id,
            "status": self.status,
            "globus_endpoint_id": self.globus_endpoint_id,
            "display_name": self.display_name,
            "config_data": self.get_config_data(),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
