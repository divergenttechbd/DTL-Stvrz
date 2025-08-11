from rest_framework import serializers
from .models import Link

class LinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Link
        fields = ['id','code','title','target_url','deep_link_scheme','ios_store_url','android_store_url','meta','is_active','expire_at','clicks','created_at']
        read_only_fields = ['clicks','created_at']
