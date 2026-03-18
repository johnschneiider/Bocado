from functools import wraps
from time import time

from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(max_requests: int, window_seconds: int = 60):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(view_instance, request, *args, **kwargs):
            ip = _get_client_ip(request)
            key = f"ratelimit:{view_func.__name__}:{ip}"

            data = cache.get(key)
            if data is None:
                data = {"count": 0, "window_start": time()}

            elapsed = time() - data["window_start"]
            if elapsed >= window_seconds:
                data = {"count": 0, "window_start": time()}

            data["count"] += 1
            cache.set(key, data, window_seconds)

            remaining = max(0, max_requests - data["count"])
            response = view_func(view_instance, request, *args, **kwargs)

            if hasattr(response, "__setitem__"):
                response["X-RateLimit-Limit"] = str(max_requests)
                response["X-RateLimit-Remaining"] = str(remaining)

            if data["count"] > max_requests:
                if request.headers.get("Accept") == "application/json":
                    return JsonResponse(
                        {"error": "Demasiadas solicitudes. Intente mas tarde."},
                        status=429,
                    )
                return JsonResponse(
                    {"error": "Demasiadas solicitudes. Intente mas tarde."},
                    status=429,
                )

            return response

        return wrapped
    return decorator


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
