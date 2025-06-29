from django.urls import path
from maps.views import (
    get_map_place_suggestions,
    get_place_info_by_id,
    get_address_by_lat_lng, DistrictListAPIView, SubDistrictListByDistrictAPIView,
)

app_name = "maps"

urlpatterns = [
    path(
        "suggestions/",
        get_map_place_suggestions,
        name="get_map_place_suggestions",
    ),
    path(
        "places/<str:place_id>/",
        get_place_info_by_id,
        name="get_map_place_detail_by_place_id",
    ),
    path(
        "addresses/",
        get_address_by_lat_lng,
        name="get_address_by_lat_lng",
    ),

    path(
        "get-district-points/",
        DistrictListAPIView.as_view(),
        name="district_list",
    ),

    path('api/sub-districts-by-district/', SubDistrictListByDistrictAPIView.as_view(), name='sub-districts-by-district'),
]
