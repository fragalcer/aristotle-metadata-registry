from django.conf.urls import include, url

urlpatterns = [
    url(r'^issues/', include('aristotle_mdr_api.v4.issues.urls', namespace='issues')),
    url(r'^reviews/', include('aristotle_mdr_api.v4.reviews.urls', namespace='reviews')),
]
