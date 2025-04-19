import json
import os


def init_progress_json(temp, mode):
    if not os.path.exists(f"{temp}/progress.json"):

        if mode == "u":
            progress = {
                "encode": [
                    {"is_encode": False, "percent": 0, "completed_chucks_indexes": []},
                    {"is_composite_video": False}
                ],
                "upload": [
                    {"is_upload_cover": False},
                    {"is_preupload_video": False},
                    {"is_init_upload_session": False},
                    {"is_upload_chunks": False},
                    {"is_complete_upload": False},
                    {"is_submit_video": False}
                ],
            }
        elif mode == "d":
            progress = {
                "decode": [
                    {"is_decode": False, "percent": 0, "completed_chucks_indexes": []},
                    {"is_wirte_file": False}
                ],
                "download": [
                    {"is_download": False, "percent": 0, "download_speed": 0, "total_length": 0},

                ],
            }
        write_progress_json(temp, progress)
        return read_progress_json(temp)
    else:
        return read_progress_json(temp)


def read_progress_json(temp):
    with open(f"{temp}/progress.json", "r") as f:
        return json.loads(f.read())

def write_progress_json(temp, progress):
    with open(f"{temp}/progress.json", "w") as f:
        json.dump(progress, f)
