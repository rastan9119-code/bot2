from telegram import ReplyKeyboardMarkup


def admin_keyboard():
    keyboard = [
        ["📊 آمار کاربران"],
        ["💰 بررسی پرداخت ها"],
        ["🌐 سرورها"],
        ["🎫 تیکت ها"],
        ["🎵 مدیریت موزیک"],
        ["🔙 بازگشت"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )
