# myapp/middleware.py

class OverrideCOOPMiddleware:
    """
    Overrides COOP header for Facebook popup compatibility.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Apply to pages where the FB Login popup is launched
        response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
        return response