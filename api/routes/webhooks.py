import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from ninja import Router
from ninja.responses import Response
from paystack.webhook import Webhook

from api.models import Account, Transaction

logger = logging.getLogger(__name__)

router = Router()


@csrf_exempt
@router.post(
    "/paystack",
    url_name="webhook-paystack",
    auth=None,
    include_in_schema=False,
    summary="Paystack webhook handler",
)
def paystack_webhook(request):
    """Handle Paystack webhook events (charge.success)."""
    if not settings.PAYSTACK_SECRET_KEY:
        return Response({"status": "Paystack is not configured"}, status=501)

    payload_bytes = request.body
    signature = request.headers.get("X-Paystack-Signature", "")

    try:
        webhook = Webhook()
        event = webhook.verify_payload(
            payload_bytes, signature, settings.PAYSTACK_SECRET_KEY
        )
    except Exception as e:
        logger.warning(f"Webhook verification failed: {e}")
        return Response({"status": "verification failed"}, status=400)

    if event.event != "charge.success":
        logger.info(f"Ignoring webhook event: {event.event}")
        return Response({"status": "ignored"})

    reference = event.data.get("reference")
    if not reference:
        logger.warning("Webhook missing reference")
        return Response({"status": "missing reference"}, status=400)

    try:
        with transaction.atomic():
            tx = Transaction.objects.select_for_update().get(reference=reference)

            if tx.status == Transaction.Status.SUCCESS:
                logger.info(f"Transaction {reference} already processed")
                return Response({"status": "already processed"})

            if tx.status != Transaction.Status.PENDING:
                logger.warning(
                    f"Transaction {reference} in unexpected state: {tx.status}"
                )
                return Response({"status": "invalid state"}, status=400)

            account = Account.objects.select_for_update().get(id=tx.account.id)
            account.balance += tx.amount
            account.save()

            tx.status = Transaction.Status.SUCCESS
            tx.paid_at = timezone.now()
            tx.save()

        logger.info(f"Deposit completed: ref={reference}, amount={tx.amount}")
        return Response({"status": "success"})

    except Transaction.DoesNotExist:
        logger.warning(f"Transaction not found for reference: {reference}")
        return Response({"status": "transaction not found"}, status=404)
    except DatabaseError as e:
        logger.error(f"Database error processing webhook: {e}")
        return Response({"status": "database error"}, status=500)
