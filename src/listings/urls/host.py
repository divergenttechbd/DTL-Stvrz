from django.urls import path

from listings.views.host import (
    HostListingListCreateAPIView,
    HostListingRetrieveUpdateAPIView,
    HostListingConfigurationApiView,
    HostListingCalendarApiView, ManageListingCoHostsAPIView, PrimaryHostCoHostAssignmentsListView,
    PrimaryHostViewCoHostAssignmentsStatusAPIView, ListCoHostsForListingAPIView, MyCoHostedListingsAPIView,
    HostListingHardDeleteAPIView,
)

app_name = "host"

urlpatterns = [
    path(
        "configurations/",
        HostListingConfigurationApiView.as_view(),
        name="listing_configurations",
    ),
    path(
        "listings/",
        HostListingListCreateAPIView.as_view(),
        name="listing_list_create",
    ),
    path(
        "listings/<uuid:unique_id>/",
        HostListingRetrieveUpdateAPIView.as_view(),
        name="listing_retrieve_update",
    ),
    path(
        "listing-calendars/<int:listing_id>/",
        HostListingCalendarApiView.as_view(),
        name="listing_calendar",
    ),

    path('manage-cohosts/', ManageListingCoHostsAPIView.as_view(), name='manage_listing_cohosts'),
    path('my-cohost-assignments/', PrimaryHostCoHostAssignmentsListView.as_view(), name='my_primary_cohost_assignments'),

path('primary-host/cohost-assignment-status/', PrimaryHostViewCoHostAssignmentsStatusAPIView.as_view(), name='primary_host_cohost_assignment_status'),
path('listing/active-cohosts/', ListCoHostsForListingAPIView.as_view(), name='listing_active_cohosts'),
path('my-assignments/cohosting-listings/', MyCoHostedListingsAPIView.as_view(), name='my_cohosted_listings'),
path('co-hosts/manage-assignments/<int:assignment_id>/', ManageListingCoHostsAPIView.as_view(), name='cohost-manage-single'),

    path('listings/<int:pk>/hard-delete/', HostListingHardDeleteAPIView.as_view(), name='host-listing-hard-delete'),

]

