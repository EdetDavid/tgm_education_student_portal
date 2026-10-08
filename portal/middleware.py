from django.utils.cache import add_never_cache_headers


class PrivateApiMiddleware:
    """Never cache API responses or session tokens on a shared CDN."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            add_never_cache_headers(response)
        return response
