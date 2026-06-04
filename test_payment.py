from payments import *

create_payment(
    123456,
    50000,
    "TEST_FILE"
)

print(
    get_pending_payments()
)
