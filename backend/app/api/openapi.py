from fastapi.openapi.utils import get_openapi

from app.domain.documents import DocumentInput


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
            if not (
                path.startswith("/api/v2/cases")
                or path.startswith("/api/v2/client-config")
                or path.startswith("/api/v2/auth")
                or path.startswith("/api/v2/runs")
                or path.startswith("/api/v2/documents")
                or path.startswith("/api/v2/evidence")
                or path.startswith("/api/v2/measurement")
                or path.startswith("/api/v2/prototype")
            ):
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
        document_schema = DocumentInput.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        definitions = document_schema.pop("$defs", {})
        schema["components"].setdefault("schemas", {}).update(definitions)
        schema["components"]["schemas"]["DocumentInput"] = document_schema
        schema["paths"]["/api/v2/documents"]["post"]["requestBody"]["content"][
            "multipart/form-data"
        ]["schema"]["properties"]["metadata"][
            "description"
        ] = "UTF-8 JSON string conforming to DocumentInput schema; document_id adds an owned document version"
        app.openapi_schema = schema
        return schema

    app.openapi = build
