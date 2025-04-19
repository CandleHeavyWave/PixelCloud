import json
import os
import random
import string
import threading
import time

from aria2 import Aria2
from coder import decode, encode
from tool.api_request import ApiRequest
from tool.progress_json import init_progress_json
from .biliDown import BiliBiliDownloader
from .biliLogin import BiliBiliLogin
from .biliUp import BiliUploader
from .web_singer import WbiSigner


class BiliPan:
    def __init__(self, setting):
        self.setting = setting
        self.cookie_info = self._get_cookie_info()
        self.api_request = ApiRequest(self.setting)
        self.wbi_signer = WbiSigner()
        self.aria2 = Aria2.Aria2(setting)

        self.uploaders = []
        self.downloaders = []
        self.pan_json = {}

    def _get_cookie_info(self):
        bili_login = BiliBiliLogin(self.setting)
        return bili_login.get_cookies_info()

    def _fetch_space_videos(self):
        mid = self.cookie_info[self.setting.read_now_cookie()]["mid"]
        signed_params = self._sign_api_params({"mid": mid})

        response = self.api_request.get_response(
            "GET",
            self.setting.get_config("API", "space_videos"),
            params=signed_params
        )
        return response.get("data", {}).get("list", {}).get("vlist", [])


    def _sign_api_params(self, params):
        return self.wbi_signer.sign(params)

    def _create_task_id(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def _ensure_temp_directory(self, task_id, mode):
        temp_path = os.path.join("temp", task_id)
        os.makedirs(temp_path, exist_ok=True)

        if mode == "upload":
            output_path = os.path.join(temp_path, "output")
            os.makedirs(output_path, exist_ok=True)

        img_path = os.path.join(temp_path, "img")
        os.makedirs(img_path, exist_ok=True)

        return temp_path

    def _init_task(self, file_path, mode):
        task_id = self._create_task_id()
        temp_path = self._ensure_temp_directory(task_id, mode)
        progress = init_progress_json(temp_path, "u" if mode == "upload" else "d")

        task_info = {
            "id": task_id,
            "file": file_path,
            "temp": temp_path,
            "progress": progress
        }

        if mode == "upload":
            self.uploaders.append(task_info)
        else:
            self.downloaders.append(task_info)

        return task_id

    def _handle_upload(self, task_id, file_path, mode):
        task_info = next((u for u in self.uploaders if u["id"] == task_id), None)
        if not task_info:
            return

        temp_path = task_info["temp"]
        progress = task_info["progress"]

        encoder = encode.QRender(
            task_id,
            file_path,
            temp_path,
            self.setting,
            progress,
            mode
        )
        encoder.execute()
        video_path = encoder.result_path()

        uploader = BiliUploader(
            video_path,
            temp_path,
            progress,
            mode,
            self.cookie_info,
            self.setting
        )
        uploader.upload_video()

    def upload_file(self, file_path, mode="normal"):
        task_id = self._init_task(file_path, "upload")
        upload_thread = threading.Thread(
            target=self._handle_upload,
            args=(task_id, file_path, mode)
        )
        upload_thread.start()
        return task_id

    def _handle_download(self, task_id, url, out_path, file_name):
        task_info = next((d for d in self.downloaders if d["id"] == task_id), None)
        if not task_info:
            return

        temp_path = task_info["temp"]
        progress = task_info["progress"]

        downloader = BiliBiliDownloader(url, self.aria2, self.setting)
        download_dir = downloader.start_download(temp_path, progress)

        if download_dir:
            decoder = decode.QRDecoder(
                task_id,
                download_dir,
                out_path,
                "f9.jpg",
                temp_path,
                progress,
                self.setting
            )
            decoder.execute()

    def download_file(self, video_url, out_path, file_name):
        task_id = self._init_task(video_url, "download")
        download_thread = threading.Thread(
            target=self._handle_download,
            args=(task_id, video_url, out_path, file_name)
        )
        download_thread.start()
        return task_id