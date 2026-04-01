"""Static service metadata for the Online Boutique demo app."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_APP_ROOT = ROOT / "sample-app" / "src"


@dataclass(slots=True)
class ServiceInfo:
    service: str
    deployment: str
    source_path: str | None = None
    language: str = "unknown"
    file_hints: list[str] = field(default_factory=list)


CATALOG: dict[str, ServiceInfo] = {
    "adservice": ServiceInfo("adservice", "adservice", str(SAMPLE_APP_ROOT / "adservice"), "java", ["src/main/java/hipstershop/AdService.java"]),
    "cartservice": ServiceInfo("cartservice", "cartservice", str(SAMPLE_APP_ROOT / "cartservice"), "csharp", ["src/services/CartService.cs", "src/Program.cs"]),
    "checkoutservice": ServiceInfo("checkoutservice", "checkoutservice", str(SAMPLE_APP_ROOT / "checkoutservice"), "go", ["main.go", "money/money.go"]),
    "currencyservice": ServiceInfo("currencyservice", "currencyservice", str(SAMPLE_APP_ROOT / "currencyservice"), "node", ["server.js", "client.js"]),
    "emailservice": ServiceInfo("emailservice", "emailservice", str(SAMPLE_APP_ROOT / "emailservice"), "python", ["email_server.py"]),
    "frontend": ServiceInfo("frontend", "frontend", str(SAMPLE_APP_ROOT / "frontend"), "go", ["main.go", "handlers.go", "middleware.go"]),
    "paymentservice": ServiceInfo("paymentservice", "paymentservice", str(SAMPLE_APP_ROOT / "paymentservice"), "node", ["server.js", "charge.js"]),
    "productcatalogservice": ServiceInfo("productcatalogservice", "productcatalogservice", str(SAMPLE_APP_ROOT / "productcatalogservice"), "go", ["server.go", "product_catalog.go"]),
    "recommendationservice": ServiceInfo("recommendationservice", "recommendationservice", str(SAMPLE_APP_ROOT / "recommendationservice"), "python", ["recommendation_server.py"]),
    "shippingservice": ServiceInfo("shippingservice", "shippingservice", str(SAMPLE_APP_ROOT / "shippingservice"), "go", ["main.go", "quote.go"]),
}


def get_service_info(service: str) -> ServiceInfo:
    return CATALOG.get(service, ServiceInfo(service, service))
