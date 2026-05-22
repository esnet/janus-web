import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GlobusToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token_data",
                    models.TextField(
                        help_text="JSON-serialized Globus token response (access_token, refresh_token, expiry, scopes)"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="globus_token",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Globus Token",
                "verbose_name_plural": "Globus Tokens",
            },
        ),
        migrations.CreateModel(
            name="GlobusService",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "session_id",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        help_text="Janus Controller session ID hosting the GCS container",
                    ),
                ),
                (
                    "node_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        help_text="Janus node name where the GCS container is running",
                    ),
                ),
                (
                    "container_id",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        help_text="Container ID of the GCS container",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("auth_complete", "Auth Complete"),
                            ("endpoint_configured", "Endpoint Configured"),
                            ("node_configured", "Node Configured"),
                            ("gateway_configured", "Gateway Configured"),
                            ("collections_configured", "Collections Configured"),
                            ("complete", "Complete"),
                            ("error", "Error"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                (
                    "globus_endpoint_id",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        help_text="Globus endpoint UUID (populated after endpoint setup)",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        help_text="Human-readable display name for the GCS endpoint",
                    ),
                ),
                (
                    "config_data",
                    models.TextField(
                        blank=True,
                        default="{}",
                        help_text="JSON-serialized configuration data collected across wizard steps",
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Last error message if status=error",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="globus_services",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Globus Service",
                "verbose_name_plural": "Globus Services",
                "ordering": ["-created_at"],
            },
        ),
    ]
