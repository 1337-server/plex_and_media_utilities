import urllib.request
import json
from getfilelistpy import getfilelist
from os import path, makedirs, remove, rename


def download_googledrive_folder(remote_folder, local_dir, gdrive_api_key, debug_en):
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
            if not path.exists(destination):
                print("path doesnt exist")
                makedirs(destination)
            print(json.dumps(res))
            for folder in res['fileList']:
                print(folder)
                for file_dict in folder['files']:
                    print(f"Downloading {file_dict['name']}")
                    if gdrive_api_key:
                        source = f"https://www.googleapis.com/drive/v3/files/{file_dict['id']}" \
                                 f"?alt=media&key={gdrive_api_key} "
                    else:
                        # only works for small files (<100MB)
                        source = f"https://drive.google.com/uc?id={file_dict['id']}&export=download"
                    destination_file = path.join(destination, file_dict['name'])
                    if urllib.request.urlretrieve(source, destination_file):
                        print("file downloaded")
                    else:
                        print("download failed")

        except Exception as err:
            print("error", err)
            success = False

    return success
