import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from django.core.exceptions import ObjectDoesNotExist
from ninja import Router
from ninja.responses import Response
from decimal import Decimal

from paystack import PaystackClient, PaystackError, TransactionFailureError

from api.auth import JWTAuth
from api.models import Account, Transaction
from api.schemas import (
    DepositRequest,
    DepositResponse,
    WithdrawRequest,
    TransferRequest,
    BalanceResponse,
    MessageResponse,
    TransactionStatusResponse,
)
from api.exceptions import InvalidRequestException

logger = logging.getLogger(__name__)
router = Router(auth=JWTAuth())
pc = PaystackClient(
    secret_key=settings.PAYSTACK_SECRET_KEY,
    base_url="https://api.paystack.co",
)


@router.get(
    "/transactions/{reference}",
    response=TransactionStatusResponse,
    url_name="transaction-status",
    summary="Check transaction status",
)
def transaction_status(request, reference: str):
    """Check the status of a transaction by reference.

    Returns the transaction from our database. For a live status
    from Paystack use the /transactions/{reference}/verify endpoint.
    """
    try:
        account = Account.objects.get(user=request.auth)
        tx = Transaction.objects.get(reference=reference, account=account)
    except (Account.DoesNotExist, Transaction.DoesNotExist):
        raise InvalidRequestException("Transaction not found")

    return Response({
        "reference": tx.reference,
        "status": tx.status,
        "amount": tx.amount,
        "type": tx.type,
        "paid_at": tx.paid_at.isoformat() if tx.paid_at else None,
        "created_at": tx.created_at.isoformat(),
    },
    status=200
    )


@router.get(
    "/transactions/{reference}/verify",
    response=TransactionStatusResponse,
    url_name="transaction-verify",
    summary="Verify transaction with Paystack",
)
def transaction_verify(request, reference: str):
    """Verify a transaction directly with Paystack.

    Queries Paystack for the live transaction status and updates
    our database record if it exists and the status has changed.
    Useful for polling after Paystack redirects the user back.
    """
    try:
        data, _ = pc.transactions.verify(reference=reference)
    except TransactionFailureError:
        return Response({
            "reference": reference,
            "status": "failed",
            "amount": Decimal(0),
            "type": "deposit",
            "paid_at": None,
            "created_at": "",
        })
    except PaystackError:
        return Response({"detail": "Transaction not found"}, status=404)

    amount_kobo = data.get("amount", 0)
    amount_naira = Decimal(amount_kobo) / Decimal(100)
    remote_status = data.get("status", "unknown")
    remote_paid_at = data.get("paid_at")

    try:
        account = Account.objects.get(user=request.auth)
        tx = Transaction.objects.get(reference=reference, account=account)
        if tx.status != remote_status:
            tx.status = remote_status
            if remote_paid_at:
                tx.paid_at = remote_paid_at
            tx.save(update_fields=["status", "paid_at"])
    except (Account.DoesNotExist, Transaction.DoesNotExist):
        pass

    return Response({
        "reference": reference,
        "status": remote_status,
        "amount": amount_naira,
        "type": "deposit",
        "paid_at": remote_paid_at,
        "created_at": data.get("created_at", ""),
    })


@router.get(
    "/balance",
    response=BalanceResponse,
    url_name="account-balance",
    summary="Get account balance",
)
def get_balance(request):
    """Retrieve your current account balance."""
    account = Account.objects.get(user=request.auth)
    return Response({"balance": account.balance}, status=200)


@router.post(
    "/deposit",
    response=DepositResponse,
    url_name="account-deposit",
    summary="Initiate deposit via Paystack",
)
def deposit(request, payload: DepositRequest):
    """Initiate a Paystack payment to deposit funds into your account.

    Amount is in Naira. Converts to kobo for Paystack (1 Naira = 100 kobo).
    Returns an authorization URL to redirect the user to Paystack's checkout.
    """
    user = request.auth
    amount_ngn = payload.amount
    amount_kobo = int(amount_ngn * 100)

    if amount_kobo < 5000:
        raise InvalidRequestException("Minimum deposit is ₦50")

    if not settings.PAYSTACK_SECRET_KEY:
        return Response(
            {"detail": "Deposits are not available: Paystack is not configured"},
            status=501,
        )

    try:
        account = Account.objects.get(user=user)
    except Account.DoesNotExist:
        return Response({"detail": "Account not found"}, status=503)

    callback_url = payload.callback_url or settings.CALLBACK_URL or None

    try:
        data, _ = pc.transactions.initialize(
            amount=amount_kobo,
            email=user.email,
            currency="NGN",
            callback_url=callback_url,
        )
    except PaystackError as e:
        logger.error(f"Paystack init error: {e}")
        return Response(
            {"detail": "Payment service temporarily unavailable. Please try again later."},
            status=503
        )

    try:
        transaction = Transaction.objects.create(
            account=account,
            type=Transaction.Type.DEPOSIT,
            amount=amount_ngn,
            reference=data["reference"],
            status=Transaction.Status.PENDING,
            authorization_url=data["authorization_url"],
        )
        logger.info(f"Deposit initiated: ref={transaction.reference}")
        return Response({
            "authorization_url": transaction.authorization_url,
            "reference": transaction.reference,
        },
        status=202
        )
    except DatabaseError as e:
        logger.error(f"Database error creating transaction: {e}")
        return Response({"detail": "Failed to create transaction"}, status=500)


@router.post(
    "/withdraw",
    response=MessageResponse,
    url_name="account-withdraw",
    summary="Withdraw funds from account",
)
def withdraw(request, payload: WithdrawRequest):
    """Withdraw funds from your account. Requires sufficient balance."""
    user = request.auth
    amount = payload.amount

    try:
        with transaction.atomic():
            account = Account.objects.select_for_update().get(user=user)

            if account.balance < amount:
                raise InvalidRequestException("Insufficient funds")

            account.balance -= amount
            account.save()

            _ = Transaction.objects.create(
                account=account,
                type=Transaction.Type.WITHDRAWAL,
                amount=amount,
                status=Transaction.Status.SUCCESS,
            )

        return Response(
            {"message": "Withdrawal successful", "new_balance": account.balance},
            status=202,
        )

    except DatabaseError as e:
        logger.error(f"Database error during withdrawal: {e}")
        return Response({"detail": "Withdrawal failed"}, status=500)


@router.post(
    "/transfer",
    response=MessageResponse,
    url_name="account-transfer",
    summary="Transfer funds to another user",
)
def transfer(request, payload: TransferRequest):
    """Transfer funds to another registered user's account.

    Amount is in Naira. Self-transfers are rejected.
    Both accounts are locked atomically to prevent race conditions.
    """
    user = request.auth
    amount = payload.amount
    recipient_number = payload.recipient_account_number

    try:
        with transaction.atomic():
            sender = Account.objects.select_for_update().get(user=user)

            if sender.number == recipient_number:
                raise InvalidRequestException("Cannot transfer to your own account")

            try:
                recipient = Account.objects.select_for_update().get(
                    number=recipient_number
                )
            except ObjectDoesNotExist:
                raise InvalidRequestException("Recipient account not found")

            if sender.balance < amount:
                raise InvalidRequestException("Insufficient funds")

            sender.balance -= amount
            recipient.balance += amount
            sender.save()
            recipient.save()

            _ = Transaction.objects.create(
                account=sender,
                type=Transaction.Type.TRANSFER_OUT,
                amount=amount,
                counterparty=recipient,
                status=Transaction.Status.SUCCESS,
            )

            _ = Transaction.objects.create(
                account=recipient,
                type=Transaction.Type.TRANSFER_IN,
                amount=amount,
                counterparty=sender,
                status=Transaction.Status.SUCCESS,
            )

        return Response(
            {"message": "Transfer successful", "new_balance": sender.balance},
            status=202,
        )

    except DatabaseError as e:
        logger.error(f"Database error during transfer: {e}")
        return Response({"detail": "Transfer failed"}, status=500)
