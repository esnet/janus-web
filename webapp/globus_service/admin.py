from django.contrib import admin
from .models import GlobusService, GlobusToken


@admin.register(GlobusToken)
class GlobusTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__username",)


@admin.register(GlobusService)
class GlobusServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "display_name",
        "status",
        "session_id",
        "node_name",
        "globus_endpoint_id",
        "created_at",
        "updated_at",
    )
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("user__username", "display_name", "globus_endpoint_id")
