from telegram import ReplyKeyboardMarkup


# =====================
# MAIN MENU
# =====================

def main_menu():

    keyboard = [

        ["🔱 بخش موزیک"],

        ["💣 بخش VPN"],

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =====================
# MUSIC MENU
# =====================

def music_menu():

    keyboard = [

        ["🎶 لیست آهنگ ها"],

        ["🔥 جدید و محبوب"],

        ["📈 آهنگ های ترند"],

        ["🔍 جستجوی آهنگ"],

        ["🎲 پیشنهاد رندوم"],

        ["🔙 بازگشت"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =====================
# VPN MENU
# =====================

def vpn_menu():

    keyboard = [

        ["💳 تعرفه سرورها"],

        ["🧪 سرور تست"],

        ["📞 پشتیبانی"],

        ["👛 کیف پول"],

        ["🏢 سرویس سازمانی"],

        ["🔙 بازگشت"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =====================
# WALLET MENU
# =====================

def wallet_menu():

    keyboard = [

        ["➕ افزایش موجودی"],

        ["📜 تراکنش ها"],

        ["🔙 بازگشت"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =====================
# ADMIN MENU
# =====================

def admin_menu():

    keyboard = [

        ["📊 آمار کاربران"],

        ["💰 بررسی پرداخت ها"],

        ["🌐 سرورها"],

        ["🎫 تیکت ها"],

        ["🎵 مدیریت موزیک"],

        ["🔙 بازگشت"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =====================
# OWNER MENU
# =====================

def owner_menu():

    keyboard = [

        ["👮 مدیریت ادمین ها"],

        ["📢 پیام همگانی"],

        ["⚙ تنظیمات"],

        ["📊 آمار کامل"],

        ["🔙 بازگشت"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )
