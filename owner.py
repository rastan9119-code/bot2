from roles import (
    set_vpn_admin,
    set_music_admin,
    set_support_admin,
    set_temp_owner,
    clear_all_roles,
    list_all_roles
)


def add_vpn_admin(user_id):
    set_vpn_admin(user_id, True)


def add_music_admin(user_id):
    set_music_admin(user_id, True)


def add_support_admin(user_id):
    set_support_admin(user_id, True)


def add_temp_owner(user_id):
    set_temp_owner(user_id, True)


def remove_user_roles(user_id):
    clear_all_roles(user_id)


def get_admins():
    result = []

    for row in list_all_roles():

        user_id = row[0]

        if row[2]:
            result.append(
                (
                    user_id,
                    "TEMP_OWNER"
                )
            )

        if row[3]:
            result.append(
                (
                    user_id,
                    "VPN_ADMIN"
                )
            )

        if row[4]:
            result.append(
                (
                    user_id,
                    "MUSIC_ADMIN"
                )
            )

        if row[5]:
            result.append(
                (
                    user_id,
                    "SUPPORT_ADMIN"
                )
            )

    return result
