# views.py - Enhanced with better browser deep linking support

import os
import re
from django.forms import model_to_dict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from myproject import settings
from . import models
from .models import Link, Click
from .serializers import LinkSerializer
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


# API
class LinkViewSet(viewsets.ModelViewSet):
    queryset = Link.objects.all().order_by('-created_at')
    serializer_class = LinkSerializer
    lookup_field = 'code'
    lookup_value_regex = '[^/]+'

    @action(detail=True, methods=['get'])
    def qr(self, request, code=None):
        link = self.get_object()
        data = os.getenv("APP_BASE_URL", "https://btayverz.divergenttechbd.com") + f"/r/{link.code}"
        return Response({"qr_data": data})


# Helpers
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def detect_browser_type(user_agent):
    """Enhanced browser detection for better deep linking"""
    ua = user_agent.lower()

    # In-app browsers (work better with automatic deep linking)
    in_app_patterns = [
        'wv',  # WebView
        'fbav',  # Facebook
        'fban',  # Facebook
        'instagram',
        'whatsapp',
        'telegram',
        'twitter',
        'tiktok',
        'snapchat',
        'linkedin',
    ]

    is_in_app = any(pattern in ua for pattern in in_app_patterns)

    # Standalone browsers (require user interaction)
    is_chrome = 'chrome' in ua and 'edg' not in ua
    is_safari = 'safari' in ua and 'chrome' not in ua
    is_firefox = 'firefox' in ua
    is_edge = 'edg' in ua

    is_standalone = not is_in_app and (is_chrome or is_safari or is_firefox or is_edge)

    return {
        'is_in_app': is_in_app,
        'is_standalone': is_standalone,
        'is_chrome': is_chrome,
        'is_safari': is_safari,
        'is_firefox': is_firefox,
        'is_edge': is_edge,
        'user_agent': ua
    }


def build_deep_link_with_referral(base_deep_link, referral_code):
    """Add referral code to deep link URL"""
    if not base_deep_link or not referral_code:
        return base_deep_link

    # Add referral code to deep link
    separator = '&' if '?' in base_deep_link else '?'
    return f"{base_deep_link}{separator}referral_code={referral_code}"


def build_store_url_with_referral(base_url, referral_code):
    """Add referral parameters to store URLs"""
    if not referral_code:
        return base_url

    parsed = urlparse(base_url)
    query_params = dict(parse_qsl(parsed.query))

    # Add referral tracking parameters
    if 'play.google.com' in base_url:
        # Android Play Store
        query_params[
            'referrer'] = f'utm_source=referral&utm_medium=share&utm_campaign=appReferral&referral_code={referral_code}'
    elif 'apps.apple.com' in base_url:
        # iOS App Store
        query_params['mt'] = '8'  # Mobile app
        query_params['ct'] = f'referral_{referral_code}'  # Campaign token
        query_params['pt'] = referral_code  # Provider token

    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


# Enhanced redirect endpoint
def redirect_link(request, code):
    link = get_object_or_404(Link, code=code, is_active=True)
    if link.is_expired():
        return render(request, "links/expired.html", {"link": link})

    # Record click
    Click.objects.create(
        link=link,
        ip=get_client_ip(request),
        ua=request.META.get("HTTP_USER_AGENT", ""),
        referer=request.META.get("HTTP_REFERER", "") or request.META.get("HTTP_REFERRER", "")
    )
    Link.objects.filter(pk=link.pk).update(clicks=F('clicks') + 1)
    # tst

    ua = request.META.get("HTTP_USER_AGENT", "")
    browser_info = detect_browser_type(ua)
    is_mobile = any(k in ua.lower() for k in ("iphone", "ipad", "ipod", "android", "mobile"))

    # Get referral code from query parameters
    referral_code = request.GET.get('ref') or request.GET.get('referral_code') or code

    if is_mobile:
        base = os.getenv("APP_BASE_URL", f"{request.scheme}://{request.get_host()}")

        # Check if this is a manual attempt (from browser)
        is_manual = request.GET.get('manual', '').lower() == 'true'

        # Build URLs
        universal_url = f"{base}/r/{code}"
        if referral_code:
            universal_url += f"?referral_code={referral_code}"

        ios_store_base = link.ios_store_url or getattr(settings, 'IOS_STORE_URL',
                                                       "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
        android_store_base = link.android_store_url or "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

        # Build web fallback URL with referral
        web_fallback_url = link.target_url
        if referral_code:
            parsed = urlparse(web_fallback_url)
            query_params = dict(parse_qsl(parsed.query))
            query_params['referral_code'] = referral_code
            web_fallback_url = urlunparse(parsed._replace(query=urlencode(query_params)))

        context = {
            "link": link,
            "is_ios": "iphone" in ua.lower() or "ipad" in ua.lower(),
            "is_android": "android" in ua.lower(),
            "web_fallback": web_fallback_url,
            "deep_scheme": build_deep_link_with_referral(link.deep_link_scheme or "", referral_code),
            "ios_store": build_store_url_with_referral(ios_store_base, referral_code),
            "android_store": build_store_url_with_referral(android_store_base, referral_code),
            "universal_url": universal_url,
            "referral_code": referral_code,
            "is_in_app_browser": browser_info['is_in_app'],
            "is_standalone_browser": browser_info['is_standalone'],
            "browser_type": 'chrome' if browser_info['is_chrome'] else
            'safari' if browser_info['is_safari'] else
            'firefox' if browser_info['is_firefox'] else
            'edge' if browser_info['is_edge'] else 'unknown'
        }

        print(f"Deep linking context: {context}")
        return render(request, "links/deep_redirect.html", context)
    else:
        # Desktop redirect with query params preserved
        target = link.target_url
        parsed = urlparse(target)
        query_params = dict(parse_qsl(parsed.query))
        query_params.update(request.GET.dict())

        # Add referral code if not already present
        if referral_code and 'referral_code' not in query_params:
            query_params['referral_code'] = referral_code

        new_query = urlencode(query_params)
        new_url = urlunparse(parsed._replace(query=new_query))
        return redirect(new_url)


def referral_code_json(request, code):
    """Enhanced API endpoint with better referral tracking"""
    link = get_object_or_404(Link, code=code, is_active=True)

    if link.is_expired():
        return JsonResponse({
            "status": "expired",
            "message": "The referral code has expired.",
            "code": code
        }, status=410)

    # Build store URLs with referral tracking
    ios_store_base = link.ios_store_url or getattr(settings, 'IOS_STORE_URL',
                                                   "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
    android_store_base = link.android_store_url or "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

    # Detect browser for client-side handling
    ua = request.META.get("HTTP_USER_AGENT", "")
    browser_info = detect_browser_type(ua)

    data = {
        "status": "success",
        "message": "Referral link data retrieved successfully",
        "data": {
            "code": model_to_dict(link),
            "target_url": link.target_url,
            "deep_link_scheme": link.deep_link_scheme or "",
            "ios_store_url": build_store_url_with_referral(ios_store_base, code),
            "android_store_url": build_store_url_with_referral(android_store_base, code),
            "clicks": link.clicks,
            "created_at": link.created_at,
            "expires_at": link.expire_at,
            "is_expired": link.is_expired(),
            "referral_code": code,
            "browser_info": browser_info,
            "recommendations": {
                "auto_attempt": browser_info['is_in_app'],
                "require_user_interaction": browser_info['is_standalone'],
                "use_intent_url": browser_info['is_standalone'] and "android" in ua.lower(),
                "use_universal_link": browser_info['is_standalone'] and ("iphone" in ua.lower() or "ipad" in ua.lower())
            }
        }
    }
    return JsonResponse(data)


# .well-known endpoints (unchanged)
def apple_app_site_association(request):
    data = {
        "applinks": {
            "apps": [],
            "details": [{
                "appID": f"TEAMID.{os.getenv('IOS_BUNDLE_ID', 'com.stayverz.stayverz')}",
                "paths": ["/r/*"]
            }]
        }
    }
    return JsonResponse(data, safe=False)


def assetlinks_json(request):
    data = [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.stayverz.stayverz",
            "sha256_cert_fingerprints": [
                "62:1C:FE:25:00:52:FA:AB:23:E4:BD:7E:59:F3:8C:4D:9C:B0:D1:69:E1:B6:6D:96:B0:19:45:F6:82:73:D6:90",
                "EF:32:C8:91:E9:91:76:56:44:8F:49:93:C1:50:30:01:BF:F5:AC:CC:EB:A8:83:B0:D1:B0:42:F0:61:9F:F9:4D"
            ]
        }
    }]
    return JsonResponse(data, safe=False)


def web_fallback_page(request):
    """Enhanced web fallback page with referral support"""
    referral_code = request.GET.get('ref') or request.GET.get('referral_code') or request.GET.get('code')

    ios_store_base = getattr(settings, 'IOS_STORE_URL',
                             "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
    android_store_base = "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

    context = {
        'ios_store_url': build_store_url_with_referral(ios_store_base,
                                                       referral_code) if referral_code else ios_store_base,
        'android_store_url': build_store_url_with_referral(android_store_base,
                                                           referral_code) if referral_code else android_store_base,
        'referral_code': referral_code,
        'base_url': os.getenv("APP_BASE_URL", f"{request.scheme}://{request.get_host()}")
    }
    return render(request, "links/web_fallback.html", context)
