"""
Health check endpoints for Alerts Service
"""

import logging

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([])
def simple_health_check(request):
    """Ultra-simple health check for Railway"""
    return JsonResponse({"status": "healthy"}, status=200)


@api_view(["GET"])
@permission_classes([])
def health_check(request):
    """
    Detailed health check endpoint
    Checks database connection and cache availability
    """
    health_status = {
        "service": "alerts",
        "status": "healthy",
        "checks": {},
    }

    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check cache connection
    try:
        from django.core.cache import cache

        cache.set("health_check", "ok", 10)
        result = cache.get("health_check")
        if result == "ok":
            health_status["checks"]["cache"] = {"status": "healthy"}
        else:
            health_status["checks"]["cache"] = {
                "status": "unhealthy",
                "error": "Cache write/read failed",
            }
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        health_status["status"] = "degraded"
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check Celery
    try:
        from config.celery import app as celery_app

        # Check if Celery is configured
        if celery_app:
            health_status["checks"]["celery"] = {"status": "configured"}
        else:
            health_status["checks"]["celery"] = {"status": "not_configured"}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        health_status["checks"]["celery"] = {
            "status": "error",
            "error": str(e),
        }

    # Determine HTTP status code
    if health_status["status"] == "healthy":
        status_code = 200
    elif health_status["status"] == "degraded":
        status_code = 200  # Still operational
    else:
        status_code = 503

    return JsonResponse(health_status, status=status_code)


@api_view(["GET"])
@permission_classes([])
def readiness_check(request):
    """
    Readiness check - determines if service is ready to accept traffic
    """
    try:
        # Check if database is accessible
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return JsonResponse(
            {
                "status": "ready",
                "service": "alerts",
            },
            status=200,
        )

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse(
            {
                "status": "not_ready",
                "service": "alerts",
                "error": str(e),
            },
            status=503,
        )


@api_view(["GET"])
@permission_classes([])
def liveness_check(request):
    """
    Liveness check - determines if service is alive
    """
    return JsonResponse(
        {
            "status": "alive",
            "service": "alerts",
        },
        status=200,
    )
