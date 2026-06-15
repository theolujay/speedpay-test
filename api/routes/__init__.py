from ninja import NinjaAPI
from api.exceptions import api_exception_handler
from . import auth, account, admin, webhooks

api = NinjaAPI(
    urls_namespace="speedpay_api",
    title="Speedpay API",
    version="0.1.0",
    description="Digital wallet API with JWT authentication",
)

api.add_exception_handler(Exception, api_exception_handler)

api.add_router("auth", auth.router, tags=["Auth"])
api.add_router("account", account.router, tags=["Account"])
api.add_router("admin", admin.router, tags=["Admin"])
api.add_router("webhooks", webhooks.router, tags=["Webhooks"])
