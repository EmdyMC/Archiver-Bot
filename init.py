import discord
from discord.ext import commands
from discord.ext import tasks
from discord import app_commands
from constants import *
import asyncio
import aiofiles
import json
import random

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)