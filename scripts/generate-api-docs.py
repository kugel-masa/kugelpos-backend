#!/usr/bin/env python3
"""
Generate API documentation from OpenAPI JSON files.

This script reads OpenAPI JSON specs and generates comprehensive Markdown
documentation with request/response models, parameters, and examples.

Usage:
    python generate-api-docs.py all          # Generate both ja and en for all services
    python generate-api-docs.py cart         # Generate both ja and en for cart only
    python generate-api-docs.py all --lang=ja    # Japanese only
    python generate-api-docs.py all --lang=en    # English only
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

# Service metadata with both languages
SERVICE_INFO = {
    "account": {
        "title_en": "Account Service",
        "title_ja": "アカウントサービス",
        "description_en": "Provides user authentication and JWT token management.",
        "description_ja": "ユーザー認証とJWTトークン管理を提供するサービスです。",
        "port": 8000
    },
    "terminal": {
        "title_en": "Terminal Service",
        "title_ja": "ターミナルサービス",
        "description_en": "Provides tenant management, store management, and terminal management functions. Manages terminal lifecycle, cash in/out operations, and staff management.",
        "description_ja": "テナント管理、店舗管理、端末管理機能を提供するサービスです。端末のライフサイクル管理、現金入出金操作、スタッフ管理を行います。",
        "port": 8001
    },
    "master-data": {
        "title_en": "Master Data Service",
        "title_ja": "マスターデータサービス",
        "description_en": "Manages reference data including product master, payment methods, tax settings, and staff information.",
        "description_ja": "商品マスター、支払方法、税金設定、スタッフ情報などの参照データを管理するサービスです。",
        "port": 8002
    },
    "cart": {
        "title_en": "Cart Service",
        "title_ja": "カートサービス",
        "description_en": "Manages shopping cart and transaction processing. Provides cart state management using state machine pattern.",
        "description_ja": "ショッピングカートとトランザクション処理を管理するサービスです。ステートマシンパターンによるカート状態管理を提供します。",
        "port": 8003
    },
    "report": {
        "title_en": "Report Service",
        "title_ja": "レポートサービス",
        "description_en": "Generates sales reports and daily summaries. Uses plugin architecture for extensibility.",
        "description_ja": "売上レポートと日次サマリーを生成するサービスです。プラグインアーキテクチャを採用しています。",
        "port": 8004
    },
    "journal": {
        "title_en": "Journal Service",
        "title_ja": "ジャーナルサービス",
        "description_en": "Stores and manages electronic journal and transaction logs.",
        "description_ja": "電子ジャーナルとトランザクションログを保存・管理するサービスです。",
        "port": 8005
    },
    "stock": {
        "title_en": "Stock Service",
        "title_ja": "在庫サービス",
        "description_en": "Manages inventory tracking. Provides snapshot functionality and reorder point management.",
        "description_ja": "在庫管理と在庫追跡を行うサービスです。スナップショット機能と発注点管理を提供します。",
        "port": 8006
    }
}

# Localized strings
STRINGS = {
    "ja": {
        "api_spec": "API仕様書",
        "overview": "概要",
        "service_info": "サービス情報",
        "port": "ポート",
        "framework": "フレームワーク",
        "database": "データベース",
        "base_url": "ベースURL",
        "local_env": "ローカル環境",
        "prod_env": "本番環境",
        "auth": "認証",
        "auth_methods": "以下の認証方法をサポートしています：",
        "api_key_auth": "APIキー認証",
        "api_key_header": "ヘッダー",
        "api_key_usage": "用途: 端末からのAPI呼び出し",
        "jwt_auth": "JWTトークン認証",
        "jwt_usage": "用途: 管理者によるシステム操作",
        "common_response": "共通レスポンス形式",
        "operation_success": "操作が正常に完了しました",
        "api_endpoints": "APIエンドポイント",
        "path_params": "パスパラメータ",
        "query_params": "クエリパラメータ",
        "request_body": "リクエストボディ",
        "request_example": "リクエスト例",
        "response": "レスポンス",
        "response_model": "レスポンスモデル",
        "data_model": "dataフィールド",
        "response_example": "レスポンス例",
        "error_codes": "エラーコード",
        "error_format": "エラーレスポンスは以下の形式で返されます：",
        "error_message": "エラーメッセージ",
        "field": "フィールド",
        "type": "型",
        "required": "必須",
        "default": "デフォルト",
        "description": "説明",
        "param": "パラメータ",
        "yes": "Yes",
        "no": "No",
        # Group names
        "system": "システム",
        "account": "アカウント",
        "tenant": "テナント",
        "store": "店舗",
        "terminal": "端末",
        "cart": "カート",
        "transaction": "トランザクション",
        "item": "商品",
        "staff": "スタッフ",
        "payment": "支払方法",
        "tax": "税金",
        "category": "カテゴリー",
        "settings": "設定",
        "report": "レポート",
        "journal": "ジャーナル",
        "stock": "在庫",
        "event": "イベント処理",
        "cache": "キャッシュ",
        "other": "その他",
    },
    "en": {
        "api_spec": "API Specification",
        "overview": "Overview",
        "service_info": "Service Information",
        "port": "Port",
        "framework": "Framework",
        "database": "Database",
        "base_url": "Base URL",
        "local_env": "Local Environment",
        "prod_env": "Production Environment",
        "auth": "Authentication",
        "auth_methods": "The following authentication methods are supported:",
        "api_key_auth": "API Key Authentication",
        "api_key_header": "Header",
        "api_key_usage": "Usage: API calls from terminals",
        "jwt_auth": "JWT Token Authentication",
        "jwt_usage": "Usage: System operations by administrators",
        "common_response": "Common Response Format",
        "operation_success": "Operation completed successfully",
        "api_endpoints": "API Endpoints",
        "path_params": "Path Parameters",
        "query_params": "Query Parameters",
        "request_body": "Request Body",
        "request_example": "Request Example",
        "response": "Response",
        "response_model": "Response Model",
        "data_model": "data Field",
        "response_example": "Response Example",
        "error_codes": "Error Codes",
        "error_format": "Error responses are returned in the following format:",
        "error_message": "Error message",
        "field": "Field",
        "type": "Type",
        "required": "Required",
        "default": "Default",
        "description": "Description",
        "param": "Parameter",
        "yes": "Yes",
        "no": "No",
        # Group names
        "system": "System",
        "account": "Account",
        "tenant": "Tenant",
        "store": "Store",
        "terminal": "Terminal",
        "cart": "Cart",
        "transaction": "Transaction",
        "item": "Item",
        "staff": "Staff",
        "payment": "Payment",
        "tax": "Tax",
        "category": "Category",
        "settings": "Settings",
        "report": "Report",
        "journal": "Journal",
        "stock": "Stock",
        "event": "Event Processing",
        "cache": "Cache",
        "other": "Other",
    }
}


def resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref reference in the OpenAPI spec."""
    if not ref.startswith("#/"):
        return {}

    parts = ref[2:].split("/")
    result = spec
    for part in parts:
        result = result.get(part, {})
    return result


def get_schema_example(spec: dict, schema: dict, depth: int = 0) -> Any:
    """Generate an example value from a schema."""
    if depth > 5:
        return "..."

    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    if "example" in schema:
        return schema["example"]

    if "default" in schema:
        return schema["default"]

    # Handle anyOf (nullable types, union types)
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            if option.get("type") != "null":
                return get_schema_example(spec, option, depth)
        return None

    schema_type = schema.get("type", "object")

    if schema_type == "object":
        properties = schema.get("properties", {})
        result = {}
        for prop_name, prop_schema in list(properties.items())[:10]:
            result[prop_name] = get_schema_example(spec, prop_schema, depth + 1)
        return result

    elif schema_type == "array":
        items = schema.get("items", {})
        return [get_schema_example(spec, items, depth + 1)]

    elif schema_type == "string":
        if "enum" in schema:
            return schema["enum"][0]
        format_type = schema.get("format", "")
        if format_type == "date-time":
            return "2025-01-01T00:00:00Z"
        if format_type == "date":
            return "2025-01-01"
        if format_type == "email":
            return "user@example.com"
        return "string"

    elif schema_type == "integer":
        return 0

    elif schema_type == "number":
        return 0.0

    elif schema_type == "boolean":
        return True

    return None


def get_type_name(spec: dict, prop_schema: dict) -> str:
    """Get a human-readable type name from a schema."""
    if "$ref" in prop_schema:
        return prop_schema["$ref"].split("/")[-1]

    # Handle anyOf (nullable types)
    if "anyOf" in prop_schema:
        for option in prop_schema["anyOf"]:
            if option.get("type") == "null":
                continue
            if "$ref" in option:
                return option["$ref"].split("/")[-1]
            if option.get("type") == "array":
                items = option.get("items", {})
                if "$ref" in items:
                    item_name = items["$ref"].split("/")[-1]
                    return f"array[{item_name}]"
                return f"array[{items.get('type', 'object')}]"
            return option.get("type", "object")

    prop_type = prop_schema.get("type", "object")
    if prop_type == "array":
        items = prop_schema.get("items", {})
        if "$ref" in items:
            item_name = items["$ref"].split("/")[-1]
            return f"array[{item_name}]"
        return f"array[{items.get('type', 'object')}]"

    return prop_type


def format_schema_properties(spec: dict, schema: dict, lang: str) -> str:
    """Format schema properties as a table."""
    s = STRINGS[lang]

    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if not properties:
        return ""

    lines = []
    lines.append(f"| {s['field']} | {s['type']} | {s['required']} | {s['description']} |")
    lines.append("|------------|------|------|------|")

    for prop_name, prop_schema in properties.items():
        prop_type = get_type_name(spec, prop_schema)
        is_required = s["yes"] if prop_name in required else s["no"]

        # Get description from resolved schema if needed
        resolved_schema = prop_schema
        if "$ref" in prop_schema:
            resolved_schema = resolve_ref(spec, prop_schema["$ref"])
        description = resolved_schema.get("description", "-")[:50]

        lines.append(f"| `{prop_name}` | {prop_type} | {is_required} | {description} |")

    return "\n".join(lines)


def get_data_model_from_response(spec: dict, resp_schema: dict) -> tuple[str, dict]:
    """Extract the data model name and schema from an API response schema.

    Returns:
        tuple: (model_name, model_schema) or (None, None) if not found
    """
    if "$ref" in resp_schema:
        resp_schema = resolve_ref(spec, resp_schema["$ref"])

    # Look for the 'data' property in the response schema
    properties = resp_schema.get("properties", {})
    data_prop = properties.get("data", {})

    if not data_prop:
        return None, None

    # Handle anyOf (nullable types)
    if "anyOf" in data_prop:
        for option in data_prop["anyOf"]:
            if "$ref" in option:
                ref = option["$ref"]
                model_name = ref.split("/")[-1]
                model_schema = resolve_ref(spec, ref)
                return model_name, model_schema
            elif option.get("type") == "array" and "items" in option:
                items = option["items"]
                if "$ref" in items:
                    ref = items["$ref"]
                    model_name = ref.split("/")[-1]
                    model_schema = resolve_ref(spec, ref)
                    return f"array[{model_name}]", model_schema

    # Direct $ref
    if "$ref" in data_prop:
        ref = data_prop["$ref"]
        model_name = ref.split("/")[-1]
        model_schema = resolve_ref(spec, ref)
        return model_name, model_schema

    # Array type
    if data_prop.get("type") == "array" and "items" in data_prop:
        items = data_prop["items"]
        if "$ref" in items:
            ref = items["$ref"]
            model_name = ref.split("/")[-1]
            model_schema = resolve_ref(spec, ref)
            return f"array[{model_name}]", model_schema

    return None, None


def generate_endpoint_docs(spec: dict, path: str, method: str, details: dict, index: int, lang: str, translations: dict = None) -> str:
    """Generate documentation for a single endpoint."""
    s = STRINGS[lang]
    lines = []

    # Title (translate if Japanese and translation exists)
    summary = details.get("summary", details.get("operationId", f"{method.upper()} {path}"))
    if lang == "ja" and translations:
        summary = translations.get("summaries", {}).get(summary, summary)
    lines.append(f"### {index}. {summary}")
    lines.append("")

    # Method and path
    lines.append(f"**{method.upper()}** `{path}`")
    lines.append("")

    # Description (translate if Japanese and translation exists)
    description = details.get("description", "")
    if description:
        # Extract first paragraph before Args:, Returns:, Raises:
        for marker in ["Args:", "Returns:", "Raises:"]:
            if marker in description:
                description = description.split(marker)[0]
        description = description.strip()

        if description:
            # Try to translate if Japanese
            if lang == "ja" and translations:
                description = translations.get("descriptions", {}).get(description, description)
            lines.append(description)
            lines.append("")

    # Path parameters
    path_params = [p for p in details.get("parameters", []) if p.get("in") == "path"]
    if path_params:
        lines.append(f"**{s['path_params']}:**")
        lines.append("")
        lines.append(f"| {s['param']} | {s['type']} | {s['required']} | {s['description']} |")
        lines.append("|------------|------|------|------|")
        for param in path_params:
            param_schema = param.get("schema", {})
            param_type = param_schema.get("type", "string")
            required = s["yes"] if param.get("required", False) else s["no"]
            desc = param.get("description", "-")
            lines.append(f"| `{param['name']}` | {param_type} | {required} | {desc} |")
        lines.append("")

    # Query parameters
    query_params = [p for p in details.get("parameters", []) if p.get("in") == "query"]
    if query_params:
        lines.append(f"**{s['query_params']}:**")
        lines.append("")
        lines.append(f"| {s['param']} | {s['type']} | {s['required']} | {s['default']} | {s['description']} |")
        lines.append("|------------|------|------|------------|------|")
        for param in query_params:
            param_schema = param.get("schema", {})
            param_type = param_schema.get("type", "string")
            required = s["yes"] if param.get("required", False) else s["no"]
            default = param_schema.get("default", "-")
            desc = param.get("description", "-")[:40]
            lines.append(f"| `{param['name']}` | {param_type} | {required} | {default} | {desc} |")
        lines.append("")

    # Request body
    request_body = details.get("requestBody", {})
    if request_body:
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        if schema:
            lines.append(f"**{s['request_body']}:**")
            lines.append("")

            # Schema table
            schema_table = format_schema_properties(spec, schema, lang)
            if schema_table:
                lines.append(schema_table)
                lines.append("")

            # Example
            example = json_content.get("example") or get_schema_example(spec, schema)
            if example:
                lines.append(f"**{s['request_example']}:**")
                lines.append("```json")
                lines.append(json.dumps(example, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")

    # Response
    responses = details.get("responses", {})
    success_response = responses.get("200") or responses.get("201") or responses.get("204")

    if success_response:
        lines.append(f"**{s['response']}:**")
        lines.append("")

        resp_content = success_response.get("content", {})
        json_resp = resp_content.get("application/json", {})
        resp_schema = json_resp.get("schema", {})

        if resp_schema:
            # Extract and document the data model
            model_name, model_schema = get_data_model_from_response(spec, resp_schema)

            if model_name and model_schema:
                lines.append(f"**{s['data_model']}:** `{model_name}`")
                lines.append("")

                # Generate table for data model properties
                model_table = format_schema_properties(spec, model_schema, lang)
                if model_table:
                    lines.append(model_table)
                    lines.append("")

            # Response example
            example = json_resp.get("example") or get_schema_example(spec, resp_schema)
            if example:
                lines.append(f"**{s['response_example']}:**")
                lines.append("```json")
                lines.append(json.dumps(example, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


def get_group_name(path: str, lang: str) -> str:
    """Determine the group name for an endpoint."""
    s = STRINGS[lang]

    if path == "/" or path == "/health":
        return s["system"]
    elif "/carts" in path:
        return s["cart"]
    elif "/transactions" in path:
        return s["transaction"]
    elif "/tenants" in path and "/stores" not in path and "/staff" not in path:
        return s["tenant"]
    elif "/stores" in path and "/stock" not in path:
        return s["store"]
    elif "/terminals" in path:
        return s["terminal"]
    elif "/staff" in path:
        return s["staff"]
    elif "/items" in path or "/item_books" in path:
        return s["item"]
    elif "/payments" in path:
        return s["payment"]
    elif "/taxes" in path:
        return s["tax"]
    elif "/categories" in path:
        return s["category"]
    elif "/settings" in path:
        return s["settings"]
    elif "/reports" in path:
        return s["report"]
    elif "/journals" in path:
        return s["journal"]
    elif "/stock" in path:
        return s["stock"]
    elif "/tranlog" in path or "/cashlog" in path or "/opencloselog" in path:
        return s["event"]
    elif "/cache" in path:
        return s["cache"]
    elif "/accounts" in path:
        return s["account"]
    else:
        return s["other"]


def generate_service_docs(service_name: str, spec: dict, lang: str, translations: dict = None) -> str:
    """Generate complete documentation for a service."""
    info = SERVICE_INFO.get(service_name, {})
    s = STRINGS[lang]

    lines = []

    # Header
    title = info.get(f"title_{lang}", service_name)
    lines.append(f"# {title} {s['api_spec']}")
    lines.append("")

    # Overview
    lines.append(f"## {s['overview']}")
    lines.append("")
    lines.append(info.get(f"description_{lang}", ""))
    lines.append("")

    # Service info
    lines.append(f"## {s['service_info']}")
    lines.append("")
    lines.append(f"- **{s['port']}**: {info.get('port', 'N/A')}")
    lines.append(f"- **{s['framework']}**: FastAPI")
    lines.append(f"- **{s['database']}**: MongoDB (Motor async driver)")
    lines.append("")

    # Base URL
    lines.append(f"## {s['base_url']}")
    lines.append("")
    lines.append(f"- {s['local_env']}: `http://localhost:{info.get('port', 8000)}`")
    lines.append(f"- {s['prod_env']}: `https://{service_name}.{{domain}}`")
    lines.append("")

    # Authentication
    lines.append(f"## {s['auth']}")
    lines.append("")
    lines.append(s['auth_methods'])
    lines.append("")
    lines.append(f"### {s['api_key_auth']}")
    lines.append(f"- {s['api_key_header']}: `X-API-Key: {{api_key}}`")
    lines.append(f"- {s['api_key_usage']}")
    lines.append("")
    lines.append(f"### {s['jwt_auth']}")
    lines.append(f"- {s['api_key_header']}: `Authorization: Bearer {{token}}`")
    lines.append(f"- {s['jwt_usage']}")
    lines.append("")

    # Common response format
    lines.append(f"## {s['common_response']}")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({
        "success": True,
        "code": 200,
        "message": s['operation_success'],
        "data": {"...": "..."},
        "operation": "operation_name"
    }, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    # API Endpoints
    lines.append(f"## {s['api_endpoints']}")
    lines.append("")

    # Sort and organize endpoints
    paths = spec.get("paths", {})
    endpoint_index = 1

    # Group endpoints by base path
    groups = {}
    for path, methods in paths.items():
        if path.startswith("/dapr"):
            continue

        group = get_group_name(path, lang)
        if group not in groups:
            groups[group] = []

        for method, details in methods.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                groups[group].append((path, method, details))

    # Define group order
    group_order = [
        s["system"], s["account"], s["tenant"], s["store"], s["terminal"],
        s["cart"], s["transaction"], s["item"], s["staff"],
        s["payment"], s["tax"], s["category"], s["settings"],
        s["report"], s["journal"], s["stock"], s["cache"],
        s["event"], s["other"]
    ]

    for group_name in group_order:
        if group_name not in groups:
            continue

        endpoints = groups[group_name]
        if not endpoints:
            continue

        lines.append(f"### {group_name}")
        lines.append("")

        # Sort by path and method
        method_order = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}
        endpoints.sort(key=lambda x: (x[0], method_order.get(x[1], 5)))

        for path, method, details in endpoints:
            doc = generate_endpoint_docs(spec, path, method, details, endpoint_index, lang, translations)
            lines.append(doc)
            endpoint_index += 1

    # Error codes
    lines.append(f"## {s['error_codes']}")
    lines.append("")
    lines.append(s['error_format'])
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({
        "success": False,
        "code": 400,
        "message": s['error_message'],
        "errorCode": "ERROR_CODE",
        "operation": "operation_name"
    }, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python generate-api-docs.py <service-name|all> [--lang=ja|en|all]")
        print("Services: account, terminal, master-data, cart, report, journal, stock")
        print("Languages: ja (Japanese), en (English), all (both)")
        sys.exit(1)

    service_arg = sys.argv[1]

    # Parse language argument
    lang_arg = "all"
    for arg in sys.argv[2:]:
        if arg.startswith("--lang="):
            lang_arg = arg.split("=")[1]

    base_dir = Path(__file__).parent.parent
    openapi_dir = base_dir / "docs" / "openapi"
    translations_file = Path(__file__).parent / "api-docs-translations.json"

    # Load translations for Japanese
    translations = None
    if translations_file.exists():
        with open(translations_file, encoding="utf-8") as f:
            translations = json.load(f)
        print(f"Loaded translations from {translations_file}")
    else:
        print(f"Warning: Translations file not found: {translations_file}")

    if service_arg == "all":
        services = list(SERVICE_INFO.keys())
    else:
        services = [service_arg]

    if lang_arg == "all":
        languages = ["ja", "en"]
    else:
        languages = [lang_arg]

    for service in services:
        openapi_file = openapi_dir / f"{service}.json"
        if not openapi_file.exists():
            print(f"Error: OpenAPI file not found: {openapi_file}")
            continue

        with open(openapi_file) as f:
            spec = json.load(f)

        for lang in languages:
            print(f"Generating {lang} docs for {service}...")

            # Only pass translations for Japanese
            lang_translations = translations if lang == "ja" else None
            docs = generate_service_docs(service, spec, lang, lang_translations)

            output_dir = base_dir / "docs" / lang / service
            output_file = output_dir / "api-specification.md"
            output_dir.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w") as f:
                f.write(docs)

            print(f"  -> {output_file}")

    print("Done!")


if __name__ == "__main__":
    main()
