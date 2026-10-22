from fastapi.openapi.utils import get_openapi


def configure_openapi(app):
    """Document security enforced by request dependencies, without exposing credentials."""

    def build():
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault("components", {})["securitySchemes"] = {
            "SessionCookie": {"type": "apiKey", "in": "cookie", "name": "xiutu_session"},
            "CSRFToken": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token"},
        }
        for path, operations in schema["paths"].items():
            if not path.startswith(("/api/v2/cases", "/api/v2/auth")):
                continue
            for method, operation in operations.items():
                if path != "/api/v2/auth/login":
                    required = {"SessionCookie": []}
                    if method == "post":
                        required["CSRFToken"] = []
                    operation["security"] = [required]
                if method == "post":
                    operation.setdefault("parameters", []).append(
                        {
                            "name": "Origin",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Must exactly equal configured APP_ORIGIN; missing or mismatched returns 403.",
                        }
                    )
        app.openapi_schema = schema
        return schema

    app.openapi = build
