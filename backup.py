import os
import shutil
from datetime import datetime
from config import DATABASE_NAME, BACKUP_FOLDER


def create_backup():
    os.makedirs(BACKUP_FOLDER, exist_ok=True)

    backup_name = os.path.join(
        BACKUP_FOLDER,
        f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )

    shutil.copy2(DATABASE_NAME, backup_name)
    return backup_name
