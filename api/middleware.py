"""Custom Django middleware for security headers, rate limiting, and CORS."""

import time
import logging
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Adds security-related HTTP headers to all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = "default-src 'self'"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "deny"
        response["X-XSS-Protection"] = "0"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimitMiddleware:
    """Limits requests per IP using a sliding window cache."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self._get_client_ip(request)
        cache_key = f"ratelimit:{ip}"
        window = 60
        max_requests = 60

        now = time.time()
        hits = cache.get(cache_key, [])

        hits = [t for t in hits if t > now - window]

        if len(hits) >= max_requests:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return JsonResponse({"detail": "Rate limit exceeded"}, status=429)

        hits.append(now)
        cache.set(cache_key, hits, timeout=window)

        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(max_requests)
        response["X-RateLimit-Remaining"] = str(max_requests - len(hits) - 1)
        return response

    def _get_client_ip(self, request):
        """Extract client IP from request headers."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class CORSMiddleware:
    """Handles CORS headers for allowed origins."""

    def __init__(self, get_response):
        self.get_response = get_response
        allowed = getattr(settings, "ALLOWED_ORIGINS", "")
        self.allowed_origins = [o.strip() for o in allowed.split(",") if o.strip()]

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN", "")

        if origin and origin in self.allowed_origins:
            response = self.get_response(request)
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Max-Age"] = "3600"
            response["Vary"] = "Origin"
        else:
            response = self.get_response(request)

        if request.method == "OPTIONS" and origin:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Max-Age"] = "3600"
            return response

        return response
