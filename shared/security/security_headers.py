"""
SECURITY HEADERS MIDDLEWARE
===========================

Adds security headers to all responses.
Protects against XSS, clickjacking, and other attacks.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: Prevents MIME sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter (legacy browsers)
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """
    
    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        frame_options: str = "DENY",
        content_type_options: bool = True,
        xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
        csp_policy: str = None,
        permissions_policy: str = None,
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy
        self.csp_policy = csp_policy
        self.permissions_policy = permissions_policy
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # X-Content-Type-Options
        if self.content_type_options:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options
        if self.frame_options:
            response.headers["X-Frame-Options"] = self.frame_options
        
        # X-XSS-Protection (legacy but still useful)
        if self.xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict-Transport-Security (HSTS)
        hsts_value = f"max-age={self.hsts_max_age}"
        if self.hsts_include_subdomains:
            hsts_value += "; includeSubDomains"
        if self.hsts_preload:
            hsts_value += "; preload"
        response.headers["Strict-Transport-Security"] = hsts_value
        
        # Referrer-Policy
        if self.referrer_policy:
            response.headers["Referrer-Policy"] = self.referrer_policy
        
        # Content-Security-Policy
        if self.csp_policy:
            response.headers["Content-Security-Policy"] = self.csp_policy
        else:
            # Default CSP for API
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'; "
                "form-action 'none'"
            )
        
        # Permissions-Policy
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy
        else:
            # Default: disable most features
            response.headers["Permissions-Policy"] = (
                "accelerometer=(), "
                "camera=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "payment=(), "
                "usb=()"
            )
        
        # Cache-Control for API responses
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        
        return response


def get_security_middleware(environment: str = "production"):
    """
    Get security middleware configured for environment.
    
    Args:
        environment: "development", "staging", or "production"
    
    Returns:
        Configured SecurityHeadersMiddleware
    """
    if environment == "development":
        # Relaxed settings for development
        return SecurityHeadersMiddleware(
            app=None,
            hsts_max_age=0,  # Disable HSTS in dev
            frame_options="SAMEORIGIN",  # Allow iframes in dev
            csp_policy="default-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src *",
        )
    
    elif environment == "staging":
        # Moderate settings for staging
        return SecurityHeadersMiddleware(
            app=None,
            hsts_max_age=86400,  # 1 day
            hsts_preload=False,
        )
    
    else:
        # Strict settings for production
        return SecurityHeadersMiddleware(
            app=None,
            hsts_max_age=31536000,  # 1 year
            hsts_include_subdomains=True,
            hsts_preload=True,
            frame_options="DENY",
        )


# ============== CORS CONFIGURATION ==============

def get_cors_config(environment: str = "production") -> dict:
    """
    Get CORS configuration for environment.
    
    Returns dict suitable for CORSMiddleware.
    """
    if environment == "development":
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
    
    elif environment == "staging":
        return {
            "allow_origins": [
                "https://dev-swat.com",
                "https://www.dev-swat.com",
                "https://api.dev-swat.com",
            ],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Request-ID",
            ],
        }
    
    else:
        return {
            "allow_origins": [
                "https://resonantgenesis.ai",
                "https://www.resonantgenesis.ai",
                "https://app.resonantgenesis.ai",
            ],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Request-ID",
            ],
            "max_age": 86400,  # 24 hours
        }


# ============== EXAMPLE USAGE ==============

"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.security.security_headers import SecurityHeadersMiddleware, get_cors_config

app = FastAPI()

# Add security headers
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS
cors_config = get_cors_config("production")
app.add_middleware(CORSMiddleware, **cors_config)
"""
