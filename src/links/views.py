import os
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
        # import qrcode
        link = self.get_object()
        data = os.getenv("APP_BASE_URL", "https://btayverz.divergenttechbd.com") + f"/r/{link.code}"
        # qr = qrcode.make(data)
        # from io import BytesIO
        # buf = BytesIO()
        # qr.save(buf, format='PNG')
        # return Response(buf.getvalue(), content_type='image/png')


# Helpers
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def build_store_url_with_referral(base_url, referral_code):
    """
    Add referral parameters to store URLs
    """
    parsed = urlparse(base_url)
    query_params = dict(parse_qsl(parsed.query))

    # Add referral tracking parameters
    referral_params = {
        'referrer': f'utm_source=referral&utm_medium=share&utm_campaign=appReferral&utm_content={referral_code}'
    }

    # For Android Play Store, we can also add custom parameters
    if 'play.google.com' in base_url:
        # You can add custom parameters that your app can read
        referral_params[
            'referrer'] = f'utm_source=referral&utm_medium=share&utm_campaign=appReferral&referral_code={referral_code}'

    query_params.update(referral_params)
    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


# Redirect endpoint with deep link fallback page
def redirect_link(request, code):
    link = get_object_or_404(Link, code=code, is_active=True)
    if link.is_expired():
        return render(request, "links/expired.html", {"link": link})

    # record click
    Click.objects.create(
        link=link,
        ip=get_client_ip(request),
        ua=request.META.get("HTTP_USER_AGENT", ""),
        referer=request.META.get("HTTP_REFERER", "") or request.META.get("HTTP_REFERRER", "")
    )
    Link.objects.filter(pk=link.pk).update(clicks=F('clicks') + 1)
    # tst

    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    is_mobile = any(k in ua for k in ("iphone", "ipad", "ipod", "android", "mobile"))

    if is_mobile:
        base = os.getenv("APP_BASE_URL", f"{request.scheme}://{request.get_host()}")
        universal_url = f"{base}/r/{code}?dl=1"

        # Build store URLs with referral tracking
        ios_store_base = link.ios_store_url or getattr(settings, 'IOS_STORE_URL',
                                                       "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
        android_store_base = link.android_store_url or "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

        context = {
            "link": link,
            "is_ios": "iphone" in ua or "ipad" in ua,
            "is_android": "android" in ua,
            "web_fallback": link.target_url,
            "deep_scheme": link.deep_link_scheme or "",
            "ios_store": build_store_url_with_referral(ios_store_base, code),
            "android_store": build_store_url_with_referral(android_store_base, code),
            "universal_url": universal_url,
            "referral_code": code
        }
        print(context, " ===== ")
        return render(request, "links/deep_redirect.html", context)
    else:
        # preserve query params
        target = link.target_url
        parsed = urlparse(target)
        q = dict(parse_qsl(parsed.query))
        q.update(request.GET.dict())
        new_query = urlencode(q)
        new = parsed._replace(query=new_query)
        return redirect(urlunparse(new))


def referral_code_json(request, code):
    link = get_object_or_404(Link, code=code, is_active=True)

    if link.is_expired():
        return JsonResponse({
            "status": "expired",
            "message": "The referral code has expired.",
            "code": code
        }, status=410)

    # Build store URLs with referral tracking for API response
    ios_store_base = link.ios_store_url or getattr(settings, 'IOS_STORE_URL',
                                                   "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
    android_store_base = link.android_store_url or "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

    data = {
        "status": "200",
        "message": "success",
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
            "referral_code": code
        }
    }
    return JsonResponse(data)


# .well-known endpoints
def apple_app_site_association(request):
    data = {
  "applinks": {
    "apps": [],
    "details": [
      {
        "appIDs": [
          "BQ3RG3G782.com.stayverz.bd"
        ],
        "paths": [
          "/r/*"
        ],
        "components": [
          {
            "/": "/*"
          }
        ]
      }
    ]
  },
  "webcredentials": {
    "apps": [
      "BQ3RG3G782.com.stayverz.bd"
    ]
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
                "1F:23:BF:4B:5E:CF:78:9F:9F:B7:E9:02:F8:B6:B1:A1:49:E1:EE:F4:A6:5B:54:E3:41:C7:FE:BC:B6:3F:35:F5",
                "62:1C:FE:25:00:52:FA:AB:23:E4:BD:7E:59:F3:8C:4D:9C:B0:D1:69:E1:B6:6D:96:B0:19:45:F6:82:73:D6:90"
            ]
        }
    }]
    return JsonResponse(data, safe=False)


def web_fallback_page(request):
    """
    A simple page to show desktop users or users who need to download the app.
    Enhanced to handle referral codes from query parameters.
    """
    # Get referral code from query parameters
    referral_code = request.GET.get('ref') or request.GET.get('referral_code') or request.GET.get('code')

    ios_store_base = getattr(settings, 'IOS_STORE_URL',
                             "https://apps.apple.com/us/app/stayverz-seamless-experience/id6748875178")
    android_store_base = "https://play.google.com/store/apps/details?id=com.stayverz.stayverz"

    context = {
        'ios_store_url': build_store_url_with_referral(ios_store_base,
                                                       referral_code) if referral_code else ios_store_base,
        'android_store_url': build_store_url_with_referral(android_store_base,
                                                           referral_code) if referral_code else android_store_base,
        'referral_code': referral_code
    }
    return render(request, "links/web_fallback.html", context)
