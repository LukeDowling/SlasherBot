from asyncio import sleep
from glob import glob

from discord import Intents, Embed
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext.commands import Bot as BotBase
from discord.ext.commands import Context
from discord.ext.commands import CommandNotFound
from discord.ext.commands import BadArgument
from discord.ext.commands import MissingRequiredArgument
from discord.ext.commands import CommandOnCooldown
from discord.ext.commands import when_mentioned_or
from discord.errors import Forbidden
from discord.errors import HTTPException



from ..db import db

OWNER_IDS = [479887202156019712]
COGS = [path.split("\\")[-1][:-3] for path in glob("./lib/cogs/*.py")]
IGNORE_EXCEPTIONS = (CommandNotFound, BadArgument)

def get_prefix(bot, message):
    if db.field("SELECT GuildID from guilds WHERE GuildID = ?", message.guild.id) is None:
        db.execute("INSERT INTO guilds (GuildID) VALUES (?)", message.guild.id)

    prefix = db.field("SELECT Prefix FROM guilds WHERE GuildID = ?", message.guild.id)

    return when_mentioned_or(prefix)(bot, message)

class Ready(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f"{cog} cog ready")

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])


class Bot(BotBase):
    def __init__(self):
        self.ready = False
        self.cogs_ready = Ready()
        self.scheduler = AsyncIOScheduler()

        db.autosave(self.scheduler)

        super().__init__(
                command_prefix=get_prefix,
                owner_ids=OWNER_IDS,
                intents=Intents.all(),
        )

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print (f"{cog} cog loaded")
            
        print("setup complete")

    def run(self, version):
        self.VERSION = version

        print("running setup...")
        self.setup()

        with open("./lib/bot/token.0", "r", encoding="utf-8") as tf:
            self.TOKEN = tf.read()

        print("running bot...")
        super().run(self.TOKEN, reconnect=True)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

        if self.ready:
            if ctx.command is not None and ctx.guild is not None:
                await self.invoke(ctx)

        else:
            await ctx.send("I'm not ready to recieve commands. Please wait a few seconds.")

    async def rules_reminder(self):
        await self.stdout.send("Add rules here")

    async def on_connect(self):
        print("bot connected")

    async def on_disconnect(self):
        print("bot disconnected")

    async def on_error(self, err, *args, **kwargs):
        if err == "on_command_error":
            await args[0].send("Something went wrong.")

        await self.stdout.send("An error occured.")    
        raise

    async def on_command_error(self, ctx, exc):
        if any([isinstance(exc, error) for error in IGNORE_EXCEPTIONS]):
            pass

        elif isinstance(exc, MissingRequiredArgument):
            await ctx.send("One or more required arguments are missing.")

        elif isinstance(exc, CommandOnCooldown):
            await ctx.send(f"That command is on {str(exc.cooldown.type).split('.')[-1]} cooldown. Try again in {exc.retry_after:,.2f} secs.")

        elif hasattr(exc, "original"):        
            if isinstance(exc.original, Forbidden):
                await ctx.send("I do not have permission to do that.")

            else:
                raise exc.original
        
        else:
            raise exc


    async def on_ready(self):
        if not self.ready:
            self.guild = self.get_guild(633569219312615425)
            self.stdout = self.get_channel(860486270580555777) 
            self.scheduler.add_job(
                    self.rules_reminder,
                    CronTrigger(day_of_week=0, hour=12,
                                minute=0, second=0)
                    )
            self.scheduler.start()

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            await self.stdout.send("Now online!")
            self.ready = True
            print("bot ready")

        else:
            print("bot reconnected")

    async def on_message(self, message):
        if not message.author.bot:
            await self.process_commands(message)


bot = Bot()
