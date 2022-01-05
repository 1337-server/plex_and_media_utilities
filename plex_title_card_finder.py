import requests
import praw
import json
import re
import os
import glob
import google_drive


###################################################################################
#                          GOOGLE DRIVE API                                       #
###################################################################################
google_drive_apikey = "GOOGLE DRIVE API KEY"

###################################################################################
#                          SONARR API KEY                                         #
###################################################################################
sonarr_apikey = 'SONAR API KEY'  ## Add your Sonarr API Key
sonarr_url = 'http://192.168.1.127'  ## Add your Sonarr URL
sonarr_port = 8989  ## Add your Sonarr Port (Default 8989)

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

GOOGLE_DRIVE_LINKS = []


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


def process_season(series_id, series_name):
    print(f"{colours.UNDERLINE + colours.HEADER}SCANNING r/PlexTitleCards... for {series_name}{colours.ENDC}")

    write_title = False
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
            pass

        elif author not in EXCLUDE_AUTH:

            if FULL_PACK_ONLY and not is_fullpack(submission.title):
                pass
            else:
                if not write_title:
                    with open("Output_Plex_TitleCards.txt", "a") as text_file:
                        text_file.write(f"\n\n\n{'#'*40} Results Found For: {series_name} {'#'*40}\n\n")
                        write_title = True

                with open("Output_Plex_TitleCards.txt", "a") as text_file:
                    text_file.write(submission.title + "\n")
                    text_file.write("     Link: " + "https://www.reddit.com" + submission.permalink + "\n")
                    text_file.write("     Author: " + author + "\n\n")
                if re.search(r'(https://drive\.google\.com\/drive.*(\n|\r|\b))', submission.url):
                    print(submission.url, "\033[93m found google drive\033[0m")
                    GOOGLE_DRIVE_LINKS.append({'name': series_name, 'url': submission.url})
                if re.search(r'mega.nz', submission.url):
                    print(submission.url, "\033[93m mega.nz found\033[0m")
                    # from mega import Mega
                    # mega = Mega()
                    # m = mega.login("junk-here@junkbox.com", "password-here")
                    # m.download_url(str(submission.url).strip())
                    # m.import_public_url(str(submission.url).strip())
                y = y + 1

    if y == 0:
        print(f"{colours.FAIL}No results found{colours.ENDC}")


def is_fullpack(submission_name):
    """Audits the submission name to detirmine if it's a single episode or a full pack"""
    return not bool(re.search('(s\d{1,4}e\d{1,4})+', str.lower(submission_name)))


def asset_exists(series_path):
    """Check if the asset folder already has assets for this series"""
    have_assets = False
    validation_path = ASSET_ROOT + series_path[series_path.rfind('/'):]
    for files in os.walk(validation_path):
        if re.search('(s\d{1,4}e\d{1,4})+', str.lower(''.join(map(str, files)))):
            have_assets = True
    return have_assets


def missing_episode_assets(series_id, series_name, series_path):
    """compare assets with expected episdoes"""
    print(f"{colours.OKGREEN}Local assets found... for {series_name}{colours.ENDC}")
    print("scanning for missing files...")
    # print(series_id)

    validation_path = ASSET_ROOT + series_path[series_path.rfind('/'):]
    print("scanning path... " + validation_path)

    response_episode = requests.get(
        f'{sonarr_url}:{sonarr_port}/api/episode?seriesID={series_id}&apikey={sonarr_apikey}')
    json_episodes = json.loads(response_episode.text)

    e = 0

    for element in json_episodes:
        season = element['seasonNumber']
        episode = element['episodeNumber']
        hasfile = element['hasFile']

        if season > 0 and hasfile:
            search_string = 'S' + str(season).zfill(2) + 'E' + str(episode).zfill(2)

            f = glob.glob(validation_path + '/' + search_string + '.*')

            if len(f) == 0:
                asset_missing = True
            else:
                for g in f:
                    if g.lower().endswith(('.png', '.jpg', '.jpeg')):
                        asset_missing = False

            if asset_missing:

                with open("Output_Plex_TitleCards_Missing.txt", "a") as text_file:

                    if e == 0:
                        text_file.write("\n" + '### Missing Files For: ' + series_name + ' ###' + "\n")

                        if PRINT_SOURCE:
                            text_file.write("\n" + str(get_source_txt(validation_path)) + "\n")
                            # get_source_txt(validation_path)

                        e = 1

                    text_file.write('S' + str(season).zfill(2) + 'E' + str(episode).zfill(2))
                    text_file.write(" is missing" + "\n")

    print('')


def get_source_txt(validation_path):
    """get contents of a text file to append to assets_missing test file"""

    source_string = validation_path + '/source.txt'
    if bool(os.path.isfile(source_string)):
        with open(source_string, 'r') as f:
            src = f.read()

        return src
        # with open("Output_Plex_TitleCards_Missing.txt", "a") as text_file:
        # text_file.write(src + "\n")


def main():
    """Kick off the primary process."""
    print("STARTED!")

    z = 0

    with open("Output_Plex_TitleCards.txt", "w") as text_file:
        text_file.write("Output for for today...\n")

    if SCAN_FOR_MISSING:
        with open("Output_Plex_TitleCards_Missing.txt", "w") as text_file:
            text_file.write("Output for for today...\n")

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
                process_season(series_id, series_name)
            z = z + 1

    print("DONE! " + str(z) + " Shows scanned!")

    if z > 0:
        print("Check your Output_Plex_TitleCards.txt file for details")

    if SCAN_FOR_MISSING:
        print("Check your Output_Plex_TitleCards_Missing.txt file for details of missing files")
    print(GOOGLE_DRIVE_LINKS)
    for item in GOOGLE_DRIVE_LINKS:
        from google_drive_downloader import GoogleDriveDownloader as gdd
        file_id = re.match(r"https://drive\.google\.com/drive/folders/(.*)\?", item['url'])
        if file_id and not DEBUG:
            print(file_id.group(1))
            google_drive.download_googledrive_folder(file_id.group(1), ASSET_ROOT + "/" + item['name'],
                                                     google_drive_apikey, False)


if __name__ == "__main__":
    DEBUG = False
    main()
