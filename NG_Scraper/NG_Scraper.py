import json
from bs4 import BeautifulSoup
import datetime
import time
import requests
import logging
import re
from slimit import ast
from slimit.parser import Parser
from slimit.visitors import nodevisitor

logging.basicConfig(filename='ng_scraper.log', filemode='w', level=logging.INFO)

# Load in our config information
config_fp = open('config.json', "r", encoding='utf-8')
configData = json.load(config_fp)
config_fp.close()

scraper_data_location = configData["scraper_data_path"]

# Interval to wait between sending reb requests to NewGrounds. Don't set this too low or you'll probably get banned
interval = 0.5
last_req = datetime.datetime.min


# When passed a URL, will open it, attempt to read it 3 times, and return a soup of the read info
# Returns soup on good read, 1 on 500 error (try again later), 2 on 400 error / bad link (throw out the link)
def fetch_soup(in_url):
    # Throttling - One request per interval (seconds)
    curr_time = datetime.datetime.now()
    global last_req
    delta_seconds = (curr_time - last_req).seconds
    last_req = datetime.datetime.now()
    if delta_seconds < interval:
        time.sleep(interval - delta_seconds)

    # Open a connection and grab the page at the current url
    try:
        page_raw = requests.get(in_url)
    except requests.exceptions.MissingSchema:
        logging.error("MissingSchema on page " + in_url + ". Removing link...")
        return 2

    # If we get a bad link, return the appropriate responses
    if int(page_raw.status_code / 100 == 5):
        logging.error('Error ' + page_raw.status_code + ' on link ' + in_url + '. Skipping...')
        return 1
    elif int(page_raw.status_code / 100 == 4):
        logging.error('Error ' + page_raw.status_code + ' on link ' + in_url + '. Removing link...')
        return 2

    # Parse the current page's html into a soup
    ret_soup = BeautifulSoup(page_raw.text, "html.parser")
    return ret_soup

# Data note: Artists are associated in json with links to their art


# Will enter the scraper_data json file and load the session data for the current session
def retrieve_data():
    fp = open(scraper_data_location, "r", encoding="utf-8")
    json_data = json.load(fp)
    fp.close()
    return json_data


# Will enter the scraper_data json file and dump updated the session data from the current session
def store_data(session_data):
    fp = open(scraper_data_location, "w", )
    json.dump(session_data, fp, ensure_ascii=False, indent=4, sort_keys=True)
    fp.close()


# Scrapes the name of an artist from their art page
def fetch_name(page_soup):
    artist_header = page_soup.find('span', {'class': 'user-header-name'})
    if artist_header is None:
        return None
    name = artist_header.find('a', {'class': 'user-link'}).text.strip()
    return name


# Searches through our dictionary to find the list of links
def find_link_list_in_json(curr, ret=None):
    if ret is None:
        ret = []
    if isinstance(curr, dict):
        for k, v in curr.items():
            if v:
                find_link_list_in_json(v, ret)
    if isinstance(curr, list):
        ret.append(curr)

    return ret


# Recursively searches a nested dictionary for links
def find_links_from_dictionary(curr_dictionary):
    ret_list = []
    list_of_link_lists = find_link_list_in_json(curr_dictionary)
    for link_list in list_of_link_lists:
        for elem in link_list:
            clean_link = re.search('<a href=\"//(.*)\" ', elem)
            ret_list.append(clean_link.group(1))

    return ret_list


# Grabs links to artworks on an artist's page
def fetch_art_links(page_soup):
    # Get the body script that contains all of the links that we need
    body_center = page_soup.find('div', {'class': 'body-center'})
    body_script = body_center.find_all('script')[1]

    ret_list = []
    # Javascript sucks. Let's let slimit parse for us
    parser = Parser()
    tree = parser.parse(body_script.text)
    for node in nodevisitor.visit(tree):
        if isinstance(node, ast.Assign) and getattr(node.left, 'value', '') != '':
            if node.left.value == '"years"':
                links_raw_json = json.loads(node.right.to_ecma())
                ret_list = find_links_from_dictionary(links_raw_json)
                break

    return ret_list


# Checks that the incoming images are of the rating we want
# Comment/uncomment lines based upon current preferences. Removing a category likely requires building list
def check_rating(art_soup):
    if art_soup.find('h2', {'class': 'rated-e'}) and configData["rating-e"] == "true":
        return True
    elif art_soup.find('h2', {'class': 'rated-t'}) and configData["rating-t"] == "true":
        return True
    elif art_soup.find('h2', {'class': 'rated-m'}) and configData["rating-m"] == "true":
        return True
    elif art_soup.find('h2', {'class': 'rated-a'}) and configData["rating-a"] == "true":
        return True
    else:
        return False


# Sifts through a fresh list of images and adds new ones to the artist list
def sift_through_image_links(fresh_list, artist_to_links, artist_deep_links):
    num_additions = 0
    # for link in fresh_list:
    for link in fresh_list:
        if link in artist_to_links:
            continue
        else:
            artist_to_links.append(link)

        art_soup = fetch_soup('https://' + link)

        # If our links are broken for some reason, just move on
        if art_soup == 1 or art_soup == 2:
            continue
        # Check that we even want what's on this page according to the current settings
        if not check_rating(art_soup):
            continue

        # Find all relevant image links on the page and add them to the artist's list (no duplicates)
        art_pods = art_soup.find_all('div', {'class': 'pod-body'})
        for body in art_pods:
            # First we find the image in the main zone
            image_class = body.find('div', {'class': 'image'})
            if image_class is not None:
                main_image = image_class.find('a').get('href')
                if main_image not in artist_deep_links:
                    artist_deep_links.append(main_image)
                    num_additions += 1
            # Now we search for any images that may be in the author's comments
            author_comments_class = body.find('div', {'id': 'author_comments'})
            if author_comments_class is not None:
                comment_images = author_comments_class.find_all('img')
                for image in comment_images:
                    aux_image = image.get('data-smartload-src')
                    if aux_image not in artist_deep_links:
                        artist_deep_links.append(aux_image)
                        num_additions += 1

    # Return the total number of new additions
    return num_additions


# Goes through all of our stored artist URLs, grabs direct links to all of the artwork, and stores them for later
def main():
    response = []
    # First, retrieve the data for the session
    session_data = retrieve_data()
    # Now get the list of URLs that we want to scrape from
    url_list = session_data["artist_urls"]

    # For every artist...
    for artist_url in url_list:
        # Get a soup of their art page
        art_page_soup = fetch_soup(artist_url)
        print("Working on: " + artist_url)
        if art_page_soup == 1:
            response.append("Couldn't add " + artist_url + " this time. Will try again later.")
            continue
        elif art_page_soup == 2:
            url_list.remove(artist_url)
            response.append("Couldn't add " + artist_url + ": Invalid URL")
            continue
        # Grab their name
        artist_name = fetch_name(art_page_soup)
        if artist_name is None:
            response.append("Couldn't add " + artist_url + ": Couldn't find any art links (Invalid URL?)")
            url_list.remove(artist_url)
            continue
        # Grab a link to every work on their art page
        art_list = fetch_art_links(art_page_soup)
        logging.info("Extracted " + str(len(art_list)) + " links from " + artist_name + "'s page")
        # If we couldn't find any art links, drop them
        if len(art_list) < 1:
            response.append("Couldn't add " + artist_url + ": Couldn't find any art links (Invalid URL?)")
            url_list.remove(artist_url)
            continue
        # If they're not already in the database, add them.
        if artist_name not in session_data:
            session_data[artist_name] = {
                                            "to_links": [],
                                            "deep_links": []
                                         }
            logging.info("Added " + artist_name + " to the database.")
            response.append("Added " + artist_name + " to the database.")
        # Go through every link we've gotten and save the raw links to images we want into the artist's dictionary
        new_additions = sift_through_image_links(art_list, session_data[artist_name]["to_links"], session_data[artist_name]["deep_links"])
        logging.info("Added " + str(new_additions) + " new images for " + artist_name)
        print("Added " + str(new_additions) + " new images for " + artist_name)
        if new_additions > 0:
            response.append("Added " + str(new_additions) + " new images for " + artist_name)

    # Save our data for next time
    store_data(session_data)

    # Return the responses if ran by bot
    return response


# Run the main
if __name__ == "__main__":
    main()
