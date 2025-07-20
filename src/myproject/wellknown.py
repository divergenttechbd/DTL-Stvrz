# In an app like core/views.py or a suitable location

from django.http import JsonResponse
import json


def assetlinks_view(request):

    data = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": "com.example.stayverz_flutter_app",
                "sha256_cert_fingerprints": [
                    "AC:BE:09:AE:B9:2F:BE:4F:35:42:36:22:70:07:04:E6:7D:6E:CD:B1:A2:C7:19:8F:FA:85:15:62:0D:20:43:C4"
                ]
            }
        }
    ]

    return JsonResponse(data, safe=False)

