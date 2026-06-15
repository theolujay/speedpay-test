#!/bin/bash
set -euo pipefail

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASS="${ADMIN_PASS:-$(openssl rand -base64 12)}"
ADMIN_FIRST="${ADMIN_FIRST:-Admin}"
ADMIN_LAST="${ADMIN_LAST:-User}"

echo "==> Copying .env.example -> .env (will not overwrite existing)"
cp -n .env.example .env 2>/dev/null || true

echo "==> Generating SECRET_KEY if missing"
if grep -q "^SECRET_KEY=$" .env 2>/dev/null; then
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s/^SECRET_KEY=$/SECRET_KEY=$(openssl rand -base64 32)/" .env
  else
    sed -i "s/^SECRET_KEY=$/SECRET_KEY=$(openssl rand -base64 32)/" .env
  fi
fi

# Demo convenience: a Paystack test key ships here (not in .env.example)
# so reviewers can test deposits immediately without signing up.
# Test keys only work in Paystack's sandbox -- no real money involved.
echo "==> Filling in Paystack test key if missing"
if grep -q "^PAYSTACK_SECRET_KEY=$" .env 2>/dev/null; then
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s/^PAYSTACK_SECRET_KEY=$/PAYSTACK_SECRET_KEY=sk_test_38b7d0fb175d5c54b4d728db1961e4625be5e64b/" .env
  else
    sed -i "s/^PAYSTACK_SECRET_KEY=$/PAYSTACK_SECRET_KEY=sk_test_38b7d0fb175d5c54b4d728db1961e4625be5e64b/" .env
  fi
fi

echo "==> Building and starting services..."
docker compose up --build -d

echo "==> Waiting for the app to be ready..."
until curl -sf http://localhost:8000/docs >/dev/null 2>&1; do
  sleep 2
done

echo "==> Creating admin user..."
docker compose exec -T app python manage.py shell -c "
from api.models import User
if not User.objects.filter(email='$ADMIN_EMAIL').exists():
    user = User.objects.create_user(
        email='$ADMIN_EMAIL',
        password='$ADMIN_PASS',
        first_name='$ADMIN_FIRST',
        last_name='$ADMIN_LAST',
    )
    user.is_admin = True
    user.save()
    print('Admin user created')
else:
    print('Admin user already exists')
"

echo ""
echo "================================"
echo "  Speedpay is ready!"
echo "================================"
echo "  API docs:  http://localhost:8000/docs"
echo "  Admin email:    $ADMIN_EMAIL"
echo "  Admin password: $ADMIN_PASS"
echo "================================"
