import requests
import praw
import json
import re
import os
import glob
from pathlib import Path


import google_drive

# TODO - Have the script skip already present files till last
###################################################################################
#                          GOOGLE DRIVE                                           #
###################################################################################
google_drive_apikey = "GOOGLE DRIVE API KEY"

# If True this uses the gdrive downloader exe
# This needs extra steps to auth when first run but appears
# its much easier to get running
USE_CMD_GDRIVE_DOWNLOADER = True
###################################################################################
#                          SONARR API KEY                                         #
###################################################################################
sonarr_apikey = 'SONAR API KEY'  # Add your Sonarr API Key
sonarr_url = 'http://192.168.1.127'  # Add your Sonarr URL
sonarr_port = 8989  # Add your Sonarr Port (Default 8989)

limit = 0  # set to 0 for no limit

###################################################################################
#                          REDDIT API KEY                                         #
###################################################################################
client_id = "REDDIT CLIENT ID"  # Add your Reddit Client ID
client_secret = "REDDIT SECRET"  # Add your Reddit Secret

####################################################################################
# Root path for your assets. Allows us to check if there are already any assets    #
####################################################################################
ASSET_ROOT = './posters'
ASSET_FILTER = True

####################################################################################
# Settings for scanning for missing episode files                                  #
####################################################################################
SCAN_FOR_MISSING = False  # Scan for missing episode files when some assets exist
INCLUDE_SPECIALS = False  # When scanning for missing episode files, include Specials/Season 00
PRINT_SOURCE = True  # if you have a source.txt file, print for output for faster checking

####################################################################################
# Create a comma separate list of users you want to exclude from the results       #
####################################################################################
EXCLUDE_AUTH = ["extrobe"]

####################################################################################
# When set to True, ignores any submissions that appear to be for a single episode #
####################################################################################
FULL_PACK_ONLY = True

####################################################################################
#                               File Names                                         #
####################################################################################
PLEX_TITLE_CARD_LINKS = "Output_Plex_TitleCards.txt"  # filename for main output
PLEX_MISSING_TITLE_CARD = "Output_Plex_TitleCards_Missing.txt"  # filename for missing items

####################################################################################
#                          DO NOT CHANGE - NOT CONFIGURABLE                        #
####################################################################################
GOOGLE_DRIVE_LINKS = []
LINKS = []


class colours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def process_season(series_name):
    print(f"{colours.UNDERLINE + colours.HEADER}SCANNING r/PlexTitleCards... for {series_name}{colours.ENDC}")

    write_title = False
    link = None
    y = 0

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8080",
        user_agent="Plex Title Card Matcher",
    )

    reddit.read_only = True

    for submission in reddit.subreddit("PlexTitleCards").search(series_name, limit=None):
        author = submission.author.name
        flair = submission.link_flair_text

        if flair is not None and bool(re.search('request|discussion', str.lower(''.join(map(str, flair))))):
            print("Flair check failed")
        elif author not in EXCLUDE_AUTH:

            if FULL_PACK_ONLY and not is_full_pack(submission.title):
                print("Full pack check failed.")
            else:
                if not write_title:
                    with open(PLEX_TITLE_CARD_LINKS, "a") as text_file:
                        text_file.write(f"\n\n\n{'#' * 40} Results Found For: {series_name} {'#' * 40}\n\n")
                        write_title = True
                if link_in_comments(submission.title):
                    print("link in comments")
                    for comment in submission.comments.list():
                        link = link_extractor(comment.body, comment.author, submission.author, series_name)
                with open(PLEX_TITLE_CARD_LINKS, "a") as text_file:
                    text_file.write(submission.title + "\n")
                    text_file.write("     Link: " + "https://www.reddit.com" + submission.permalink + "\n")
                    text_file.write("     Author: " + author + "\n")
                    if link is not None:
                        text_file.write(f"     Link from comment : {link}\n\n")

                google_drive_check(series_name, submission)
                # mega_check(submission)
                y = y + 1

    if y == 0:
        print(f"{colours.FAIL}No results found{colours.ENDC}")


def google_drive_check(series_name, submission):
    """
    Reserved for future use - Eventually used for diff actions for only gdrive links
    """
    if re.search(r'(https://drive\.google\.com/drive.*(\n|\r|\b))', submission.url):
        print(submission.url, "\033[93m found google drive\033[0m")
        # GOOGLE_DRIVE_LINKS.append({'name': series_name, 'url': submission.url})


def mega_check(submission):
    """
    WIP - Doesnt work ATM
    """
    if re.search(r'mega.nz', submission.url):
        print(submission.url, "\033[93m mega.nz found\033[0m")
        from mega import Mega
        mega = Mega()
        m = mega.login()
        m.download_url(str(submission.url).strip())
        m.import_public_url(str(submission.url).strip())


def is_full_pack(submission_name):
    """Audits the submission name to determine if it's a single episode or a full pack"""
    return not bool(re.search(r'(s\d{1,4}e\d{1,4})+', str.lower(submission_name)))


def link_in_comments(submission_name):
    """Audits the submission name to determine if the link is in a comment"""
    return bool("link in comments" in str.lower(submission_name))


def link_extractor(comment_body, comment_author, submission_author, series_name):
    link_from_comment = None
    # TODO - Need to check the api - but checking the comment vs post author kills performance
    if comment_body is None or comment_author != submission_author:
        return link_from_comment
    print(comment_body)
    comment = re.search(r"\((https?://[^\s]+)", comment_body)
    if comment:
        link_from_comment = comment.group(1)
        LINKS.append({'name': series_name, 'url': x})
    return link_from_comment


def asset_exists(series_path):
    """Check if the asset folder already has assets for this series"""
    have_assets = False
    validation_path = ASSET_ROOT + series_path[series_path.rfind('/'):]
    for files in os.walk(validation_path):
        if re.search(r'(s\d{1,4}e\d{1,4})+', str.lower(''.join(map(str, files)))):
            have_assets = True
    return have_assets


def missing_episode_assets(series_id, series_name, series_path):
    """compare assets with expected episodes"""
    asset_missing = False
    print(f"{colours.OKGREEN}Local assets found... for {series_name}{colours.ENDC}")
    print("scanning for missing files...")
    # print(series_id)

    # This will strip out the whole title sometimes
    p = Path(series_path)
    print(p.parts[2])
    validation_path = os.path.join(ASSET_ROOT, p.parts[2])
    print("scanning path... " + validation_path)

    response_episode = requests.get(
        f'{sonarr_url}:{sonarr_port}/api/episode?seriesID={series_id}&apikey={sonarr_apikey}')
    json_episodes = json.loads(response_episode.text)

    e = 0

    for element in json_episodes:
        season = str(element['seasonNumber'])
        episode = str(element['episodeNumber'])
        has_file = element['hasFile']

        if element['seasonNumber'] > 0 and has_file:
            # TODO: Make this walk through the dir and search the file names
            #  as currently leaves lots of room for errors
            search_string = f'S{season.zfill(2)}E{episode.zfill(2)}'
            f = glob.glob(f'{validation_path}/{search_string}.*')

            if len(f) == 0:
                # TODO - check diff variations of file naming conventions
                f = glob.glob(f'{validation_path}/{search_string}.*')
            print(validation_path + '/' + search_string + '.*')
            if len(f) == 0:
                asset_missing = True
            else:
                for g in f:
                    if g.lower().endswith(('.png', '.jpg', '.jpeg')):
                        asset_missing = False

            if asset_missing:

                with open(PLEX_MISSING_TITLE_CARD, "a") as text_file:

                    if e == 0:
                        text_file.write(f"\n ### Missing Files For: {series_name} ###\n")

                        if PRINT_SOURCE:
                            text_file.write(f"\n{get_source_txt(validation_path)}\n")
                            # get_source_txt(validation_path)
                        e = 1

                    text_file.write(f'S{season.zfill(2)}E{episode.zfill(2)}')
                    text_file.write(" is missing\n")

    print('')


def get_source_txt(validation_path):
    """get contents of a text file to append to assets_missing test file"""

    source_string = validation_path + '/source.txt'
    if bool(os.path.isfile(source_string)):
        with open(source_string, 'r') as f:
            src = f.read()

        return src
        # with open(PLEX_MISSING_TITLE_CARD, "a") as text_file:
        # text_file.write(src + "\n")


def main():
    """Kick off the primary process."""
    print("STARTED!")

    z = 0

    with open(PLEX_TITLE_CARD_LINKS, "w") as text_file:
        text_file.write("Output for today...\n")

    if SCAN_FOR_MISSING:
        with open(PLEX_MISSING_TITLE_CARD, "w") as text_file:
            text_file.write("Output for today...\n")

    response_series = requests.get(f'{sonarr_url}:{sonarr_port}/api/series?apikey={sonarr_apikey}')
    json_series = json.loads(response_series.text)

    for element in json_series:
        series_id = element['id']
        series_name = element['title']
        series_path = element['path']
        # For now, limit the number of files processed - remove this in the future #
        if limit == 0 or (limit > 0 and z < limit):
            ##

            if ASSET_FILTER and asset_exists(series_path):
                missing_episode_assets(series_id, series_name, series_path)
            else:
                process_season(series_name)
            z = z + 1

    print(f"DONE! {z} Shows scanned!")

    if z > 0:
        print("Check your Output_Plex_TitleCards.txt file for details")

    if SCAN_FOR_MISSING:
        print("Check your Output_Plex_TitleCards_Missing.txt file for details of missing files")

    print(LINKS)
    if USE_CMD_GDRIVE_DOWNLOADER:
        google_drive.use_cmd_downloader(LINKS, ASSET_ROOT)
    else:
        google_drive.process_mass_links(LINKS, google_drive_apikey, ASSET_ROOT)


if __name__ == "__main__":
    # x is only needed for testing
    x = [
        {'name': 'Chernobyl',
         'url': 'https://drive.google.com/drive/folders/1Uu7JWlkhpCTn_wNqt4cF4dzPRzeyMKle?usp=sharing'},
        {'name': 'Doctor Who (2005)',
         'url': 'https://drive.google.com/drive/folders/1Y0YHX50Oi5cjQ7UtJSnK66eWLtXZPUEv?usp=sharing'},
        {'name': 'Lie to Me',
         'url': 'https://drive.google.com/drive/folders/1wFaSe01pAnIIXHWt_4MlHODnwF85QDHk?usp=sharing'},
        {'name': 'Monkey',
         'url': 'https://drive.google.com/drive/folders/1nuyPBYrH00Ii1h2JPuuxG9ZsQy0IMXFu?usp=sharing'},
        {'name': 'The Vampire Diaries',
         'url': 'https://drive.google.com/drive/folders/1rIh6dzkSV29bgRAbButN-TIdjez11WwI?usp=sharing'},
        {'name': 'Seven Worlds, One Planet',
         'url': 'https://drive.google.com/drive/folders/12w96RY4JIMtVg3P6PcVlXCcNkMem_i4g?usp=sharing'},
        {'name': 'The Falcon and the Winter Soldier',
         'url': 'https://drive.google.com/drive/folders/1GZ-Gm1gCeMsa7Y3LTOkYu8bzokQu3gIZ?usp=sharing'},
        {'name': "The Handmaid's Tale",
         'url': 'https://drive.google.com/drive/folders/1suM0lrocxH9Sx95Ve5PS6UO3BeTyK0NG?usp=sharing'},
        {'name': 'Pretty Little Liars',
         'url': 'https://drive.google.com/drive/folders/1T9TWzgWe8lm6NZuAGs3oi2ycul_QkhXH?usp=sharing'},
        {'name': '9-1-1',
         'url': 'https://drive.google.com/drive/folders/11J-V3XuEaRhtCM0pJN8OjRuiMX1V_1px?usp=sharing'},
        {'name': '9-1-1',
         'url': 'https://www.dropbox.com/sh/xr1dnxl98iw15ga/AABkwBWikK2SFEDKXozfyqFia?dl=0'},
        {'name': '9-1-1',
         'url': 'https://drive.google.com/drive/folders/1yfsjm-tM9vX3737wNVTGtIWAy31z9X2c?usp=sharing'},
        {'name': 'Supergirl',
         'url': 'https://drive.google.com/drive/folders/1G_0w-E2cYr1MNsCwiVvuDD6KnLx84mWy?usp=sharing'}]
    # For testing only
    # google_drive.process_mass_links(x, google_drive_apikey, ASSET_ROOT)
    # google_drive.use_cmd_downloader(x, ASSET_ROOT)
    # exit(1)
    main()
