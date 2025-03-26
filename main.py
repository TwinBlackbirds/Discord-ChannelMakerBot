# author: michael amyotte (twinblackbirds)
# date: 8/23/24
# main implementation of the SkeletonBot discord bot


from models.Client import os, discord, Skeleton

#constant variables
# .env is loaded in models.Client import, so loading it in main.py is not necessary
TOKEN = os.environ["DISCORD_TOKEN"]

# represents 'intents' class which represents which permissions your bot is requiring for use
INTENTS = discord.Intents.all()

# run the bot
bot = Skeleton(intents=INTENTS)
bot.run(TOKEN)
