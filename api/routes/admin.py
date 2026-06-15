import logging
from typing import List

from ninja import Router

from api.auth import AdminAuth
from api.models import User
from api.schemas import AdminUserOut

logger = logging.getLogger(__name__)

router = Router(auth=AdminAuth())


@router.get(
    "/users",
    response=List[AdminUserOut],
    url_name="admin-users",
    summary="List all users (admin only)",
)
def list_users(request):
    """Retrieve all users with their account details and balances."""
    users = User.objects.select_related("account").all()
    result = []
    for user in users:
        account = getattr(user, "account", None)
        result.append(
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_admin": user.is_admin,
                "number": account.number if account else "",
                "balance": account.balance if account else 0,
            }
        )
    return result
