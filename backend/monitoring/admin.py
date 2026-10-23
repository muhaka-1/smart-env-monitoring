from django.contrib import admin

from .models import Reading


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("sensor_id", "timestamp", "value", "unit", "quality", "status")
    list_filter = ("status", "quality", "sensor_id")
    date_hierarchy = "timestamp"
