##### NewGrounds Scraper + Discord Bot

A webscraper built in BeautifulSoup to retrieve and store links from artist's /art pages on NewGrounds and a Discord bot built in Discord.py(rewrite) to interface with that scraped information.

##### Dependencies

[discord.py (rewrite)](https://github.com/Rapptz/discord.py/tree/rewrite)

[BeautifulSoup](https://github.com/waylan/beautifulsoup)

[Slimit](https://github.com/rspivak/slimit)

##### Setup

config.json needs to be moved from the defaults folder and updated with your accurate bot token, desired channel id (if you wish to limit usage to certain channels), the absolute path to your scraper_data.json, and the absolute path to your NG_Scraper folder. Because the path to scraper_data.json needs to be provided, it can be placed anywhere you like. It is suggested that you remove it from the defaults folder, however, so that it isn't overwritten by future updates.

To filter which images are being stored by the scraper, edit the rating-e/t/m/a lines to reflect which items should be grabbed. Default settings store images rated E and T, excluding images rated M and A.

##### Note

Slimit may cause console spam about unused assignments. If you experience this, the following commands should fix it

```
pip uninstall ply
pip install ply==3.4
```

