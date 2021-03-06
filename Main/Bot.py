from discord.ext import commands
import json
import random
import sys

# Load in our config information
f = open('config.json', "r", encoding='utf-8')
configData = json.load(f)
f.close()

# Make sure we know where to find our scraper
sys.path.append(configData["ng_scraper_path"])
from NG_Scraper import main as Scrape

# Start fresh with scraper data. We want to stay up to date
scraper_data = None

# Flag value to stop users from adding artists during database update
canAdd = True

# Set up the client, prefix is !
bot = commands.Bot(command_prefix='!')


# Update scraper data info from JSON
async def refresh_scraper_data():
    global scraper_data
    scraper_fp = open(configData["scraper_data_path"], 'r', encoding='utf-8')
    scraper_data = json.load(scraper_fp)
    scraper_fp.close()


# Store scraper data info back into JSON
async def store_scraper_data():
    global scraper_data
    scraper_fp = open(configData["scraper_data_path"], 'w')
    json.dump(scraper_data, scraper_fp, ensure_ascii=False, indent=4, sort_keys=True)
    scraper_fp.close()


# Actual bot happenings
@bot.event
async def on_ready():
    print('Logged in as: ' + bot.user.name + '(' + str(bot.user.id) + ')')
    print("And I'm ready to work!")
    print('--------------')


# Used to confine the bot to only spamming images in a single channel
def check_if_appropriate_channel(ctx):
    return ctx.message.channel.id == configData['desired_channel_id']


# Gets a random artist from a certain artist in the scraper db
@bot.command()
@commands.check(check_if_appropriate_channel)
async def pic(ctx, *, message: str):
    await refresh_scraper_data()

    if message in scraper_data:
        images = scraper_data[message]["deep_links"]
        if len(images) < 1:
            await ctx.send("`No images stored for " + message + " :(`")
        else:
            await ctx.send(random.choice(images))
    else:
        await ctx.send("`" + message + " is not in the database :(`")


# Adds an artist to the scraper db to be scraped next time the database is updated.
# Additions should only be /art pages on newgrounds. Scraper will try to remove poor links
@bot.command()
@commands.check(check_if_appropriate_channel)
async def add_artist(ctx, *, message: str):
    global canAdd
    if canAdd:
        await refresh_scraper_data()

        if message in scraper_data['artist_urls']:
            await ctx.send("`" + message + " is already in the database :)`")
        else:
            scraper_data['artist_urls'].append(message)
            await store_scraper_data()
            await ctx.send("`Added <" + message + "> to artist urls`")
    else:
        await ctx.send("`Database update in progress - no artists may be added until this process finishes.`")


# Lists all artists in the scraper db whose pics can be requested
@bot.command()
@commands.check(check_if_appropriate_channel)
async def artists(ctx):
    await refresh_scraper_data()

    response = ("```\nArtist list:\n")
    for artist in scraper_data.keys():
        if artist != 'artist_urls':
            response += (artist + " (" + str(len(scraper_data[artist]["deep_links"])) + " images)\n")
    await ctx.send(response + "\n```")


# Updates the bot's database by running the scraper
@bot.command()
@commands.check(check_if_appropriate_channel)
async def update_database(ctx):
    global canAdd
    await refresh_scraper_data()
    await ctx.send("`Updating Database - No artists may be added until I am finished`")
    canAdd = False
    response = await bot.loop.run_in_executor(None, Scrape)

    update_report = "```\nFinished updating database.\nUpdate summary:\n"
    for output in response:
        update_report += (output + "\n")

    canAdd = True
    await ctx.send(update_report + "\n```")


# Lists commands as well as how they should be used
@bot.command()
@commands.check(check_if_appropriate_channel)
async def commands(ctx):
    response = (
                 "```\n"
                 "!commands - Gets you this list again!\n"
                 "!add_artist [url] - Adds an artist to the database. url should be formatted <https://artist.newgrounds.com/art>\n"
                 "!pic [artist_name] - Retrieves a random image from the database by the artist passed in.\n"
                 "!artists - Lists which artists images can be requested based upon who's in the database and the amount of images we have stored.\n"
                 "!update_database - Runs the scraper to update images stored in the database\n"
                 "```"
               )

    await ctx.send(response)

# Start 'er up
bot.run(configData['token'])
