from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

def make_code():
    return get_random_string(7)

class Link(models.Model):
    code = models.SlugField(max_length=64, unique=True, default=make_code)
    target_url = models.URLField()
    deep_link_scheme = models.CharField(max_length=512, blank=True, null=True,
                                        help_text="Custom scheme e.g. myapp://open?item=123")
    ios_store_url = models.URLField(blank=True, null=True)
    android_store_url = models.URLField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    meta = models.JSONField(blank=True, null=True)
    clicks = models.BigIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    expire_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return self.expire_at and timezone.now() > self.expire_at

    def __str__(self):
        return self.code

class Click(models.Model):
    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="clicks_log")
    ip = models.GenericIPAddressField(blank=True, null=True)
    ua = models.TextField(blank=True, null=True)
    referer = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
