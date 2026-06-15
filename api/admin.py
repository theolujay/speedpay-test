"""Django admin configuration for User, Account, and Transaction models."""

from django.contrib import admin
from .models import User, Account, Transaction


class UserAdmin(admin.ModelAdmin):
    """Admin config for User model."""

    list_display = ("email", "first_name", "last_name", "is_admin", "is_active")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("is_admin", "is_active")


class AccountAdmin(admin.ModelAdmin):
    """Admin config for Account model."""

    list_display = ("number", "user", "balance", "created_at")
    search_fields = ("number", "user__email")
    list_filter = ("created_at",)


class TransactionAdmin(admin.ModelAdmin):
    """Admin config for Transaction model."""

    list_display = (
        "id",
        "account",
        "type",
        "amount",
        "status",
        "reference",
        "created_at",
    )
    search_fields = ("reference", "account__account_number", "account__user__email")
    list_filter = ("type", "status", "created_at")


admin.site.register(User, UserAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
