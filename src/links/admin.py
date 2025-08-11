from django.contrib import admin
from .models import Link, Click

@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "target_url", "clicks", "is_active", "created_at")
    search_fields = ("code","title","target_url")

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ("link","ip","created_at")
    list_filter = ("created_at",)
