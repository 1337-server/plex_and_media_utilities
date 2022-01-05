import os
import urllib.request
import re
import subprocess
import json
from time import sleep

from getfilelistpy import getfilelist
from os import path, makedirs
from ratelimiter import RateLimiter

BACKOFF_TIME = 120


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


@RateLimiter(max_calls=1, period=300)
def download_googledrive_folder(remote_folder, local_dir, gdrive_api_key, debug_en):
    print('\033[96m[DEBUG] Downloading: %s --> %s\033[0m' % (remote_folder, local_dir))

    success = True

    if debug_en:
        print('[DEBUG] Downloading: %s --> %s' % (remote_folder, local_dir))
    else:
        try:
            resource = {
                "api_key": gdrive_api_key,
                "id": remote_folder,
                "fields": "files(name,id)",
            }
            res = getfilelist.GetFileList(resource)
            print(f"Found #{res['totalNumberOfFiles']} files")
            destination = local_dir
            make_dirs(destination)
            print(json.dumps(res))
            for folder in res['fileList']:
                print(folder)
                for file_dict in folder['files']:
                    print(f"Downloading {file_dict['name']}")
                    # https://www.googleapis.com/drive/v3/files/[FILEID]/export?key=[YOUR_API_KEY]
                    if gdrive_api_key:
                        source = f"https://www.googleapis.com/drive/v3/files/{file_dict['id']}" \
                                 f"?alt=media&key={gdrive_api_key} "
                    else:
                        # only works for small files (<100MB)
                        source = f"https://drive.google.com/uc?id={file_dict['id']}&export=download"
                    destination_file = path.join(destination, file_dict['name'])
                    print(source)
                    url = source
                    grab_file(url, destination_file)
        except Exception as err:
            print("error", err)
            success = False

    return success


def make_dirs(destination):
    """

    :param destination: Destination folder to create
    :return: None

    """
    if not path.exists(destination):
        print("path doesnt exist")
        makedirs(destination)


def process_mass_links(links, google_drive_apikey, asset_root):
    for item in links:
        file_id = re.match(r"https://drive\.google\.com/drive/folders/(.*)\?", item['url'])
        if file_id:
            print(file_id.group(1))
            download_googledrive_folder(file_id.group(1), asset_root + "/" + item['name'],
                                        google_drive_apikey, False)


@RateLimiter(max_calls=5, period=150)
def grab_file(url, destination_file):
    global BACKOFF_TIME
    try:
        try:
            with urllib.request.urlopen(url) as response:
                print(response.code, url, response)
                if response.code == 200:
                    urllib.request.urlretrieve(url, destination_file)
        except urllib.error.HTTPError as e:
            BACKOFF_TIME = BACKOFF_TIME * 2
            print(f"E2 - sleeping for {BACKOFF_TIME * 2}")
            print(e.code, url, e.reason, e.headers)
            sleep(BACKOFF_TIME)
        except urllib.error.URLError as e:
            BACKOFF_TIME = BACKOFF_TIME * 2
            print(f"E3 - sleeping for {BACKOFF_TIME * 2}")
            if hasattr(e, 'reason'):
                print(e.reason, url)
            elif hasattr(e, 'code'):
                print(e.code, url)
            sleep(BACKOFF_TIME)
    except Exception as err:
        print("download failed", err)


def use_cmd_downloader(links, asset_root):
    """
    A 'lazy' way of downloading folders from google drive
    This used gdrive from https://github.com/prasmussen/gdrive
    You will need to use a browser to auth it on first run!

    On first run the python terminal will output a link, you must
    use a browser to open the link and authorise your account.

    :param links: List of links from earlier processes
    :param asset_root: String to root path
    :return: None
    """
    # ./venv/Scripts/gdrive download --recursive 1G_0w-E2cYr1MNsCwiVvuDD6KnLx84mWy

    for item in links:
        file_id = re.match(r"https://drive\.google\.com/drive/folders/(.*)\?", item['url'])
        if file_id:
            print(f"{colours.UNDERLINE + colours.HEADER}Downloading google drive link for {item['name']}"
                  f"  -- Link-id - {file_id.group(1)}{colours.ENDC}")
            cmd = f'{os.getcwd()}/venv/Scripts/gdrive download --path "{asset_root}" --recursive {file_id.group(1)}'
            print(cmd)
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in p.stdout.readlines():
                print(line.decode("utf-8"))
            retval = p.wait()
            # subprocess.call("venv/Scripts/gdrive -recursive " + file_id.group(1), shell=True)
            print(retval)
            # subprocess.run(["./venv/Scripts/gdrive", "--recursive", file_id.group(1)])
        print(colours.OKGREEN, "Finished downloading for ", item['name'], colours.ENDC)
