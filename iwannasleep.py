from init import *
import re


MENTION_RE = re.compile(r"<@!?(\d+)>")

# Discord id->username helper
async def get_username_from_id(user_id: int) -> str | None:
    """Finds the name and ID of a user using their user ID"""
    user = bot.get_user(user_id)
    if user is None:
        try:
            user = await bot.fetch_user(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    return user.display_name if hasattr(user, "display_name") else user.name


async def build_username_lookup_from_messages(messages: list[str]) -> dict[int, str]:
    """Builds a per-request cache of user_id -> username from message mentions."""
    user_ids: set[int] = set()
    for message in messages:
        for match in MENTION_RE.finditer(message):
            user_ids.add(int(match.group(1)))

    username_lookup: dict[int, str] = {}
    for user_id in user_ids:
        username = await get_username_from_id(user_id)
        if username:
            username_lookup[user_id] = username

    return username_lookup