from users import *

add_user(123456789, "testuser", "Test User")
update_last_seen(123456789)

print(get_user(123456789))
print(count_users())
print(count_today_users())
print(is_banned(123456789))
