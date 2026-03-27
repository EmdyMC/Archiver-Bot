from init import *

# Discord id->username helper
async def get_username_from_id(user_id: int) -> str:
    """Finds the name and ID of a user using their user ID"""
    return bot.get_user(user_id) or await bot.fetch_user(user_id) # sam is a dunce (thanks unde)