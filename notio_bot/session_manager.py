# notio_bot/session_manager.py

from collections import defaultdict

# Режимы: 'notes', 'calendar'
user_mode = {}  # user_id -> str
user_messages = defaultdict(list)  # user_id -> list of message_ids


async def clear_user_history(user_id: int, chat_id: int, bot, keep_last=0):
    """Удаляет сообщения пользователя и бота, кроме последних N."""
    messages = user_messages.get(user_id, [])
    for msg_id in messages[:-keep_last]:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            continue
    user_messages[user_id].clear()


async def switch_mode(user_id: int, chat_id: int, new_mode: str, bot):
    """Меняет режим и очищает чат, если он изменился."""
    current = user_mode.get(user_id)
    if current != new_mode:
        await clear_user_history(user_id, chat_id, bot)
        user_mode[user_id] = new_mode
