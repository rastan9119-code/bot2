from wallet import *

user_id = 123456789

ensure_wallet(user_id)
print("balance:", get_balance(user_id))

print("add:", add_balance(user_id, 50000, "test credit"))
print("balance:", get_balance(user_id))

ok, bal = subtract_balance(user_id, 15000, "test debit")
print("sub:", ok, bal)

print(get_wallet_transactions(user_id))
