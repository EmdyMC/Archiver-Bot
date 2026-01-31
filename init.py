import discord
from discord.ext import commands
from discord.ext import tasks
from discord import app_commands
from constants import *
from pathlib import Path
from typing import Type
from datetime import datetime, timedelta, UTC
import asyncio
import aiofiles
import json
import random
import difflib

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)