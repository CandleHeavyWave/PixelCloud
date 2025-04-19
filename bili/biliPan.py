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

        self.uploader_list = []
        self.downloader_list = []
        self.pan_json = {}

        self.aria2 = Aria2.Aria2(setting)
        self.bili_login = BiliBiliLogin(self.setting)
        self._api_resquat = ApiRequest(self.setting)

        self.get_cookie_info()

    def get_cookie_info(self) -> list:
        self.cookie_info = self.bili_login.get_cookies_info()
        return self.cookie_info

    def _get_space_videos(self):
        sapce_info = []

        mid = self.get_cookie_info()[self.setting.read_now_cookie()]["mid"]
        w = WbiSigner()
        p_params = w.sign({"mid": mid})
        p_space = self._api_resquat.get_response("GET", "https://api.bilibili.com/x/space/wbi/arc/search",
                                                params=p_params)

        if p_space["data"]["page"]["count"] > 1:

            pn = 1
            while p_space["data"]["page"]["count"] != len(sapce_info):
                params = w.sign({"mid": mid, "ps": 50, "pn": pn})
                space = self._api_resquat.get_response("GET", "https://api.bilibili.com/x/space/wbi/arc/search?",
                                                      params=params)
                for v in space["data"]["list"]["vlist"]:
                    sapce_info.append(v)

                pn += 1
                time.sleep(random.randint(1, 2))
            return sapce_info
    def _find_pan_info_video(self) -> str:
        space = self._get_space_videos()
        for s in space:
            title_json = json.loads(s["title"])

            if title_json["mode"] == "data":
                return s

    def get_pan_info(self):
            pan_video = self._find_pan_info_video()
            self.download_file(pan_video["url"], "temp", "bili_pan.json")
            with open("temp/bili_pan.json") as p:
                bili_pan = p.read()
                bili_pan_json = json.loads(bili_pan)

            return bili_pan_json

    def upload_pan_info(self):

        if not os.path.exists("temp/bili_pan.json"):
            with open("temp/bili_pan.json", "w") as f:
                json.dump({}, f)


        self.upload_file("temp/bili_pan.json", "info")

    def _create_temp_dir(self, task_id, mode):
        temp_path = os.path.join("temp", task_id)

        img_path = os.path.join(temp_path, "img")
        os.makedirs(img_path, exist_ok=True)

        if mode == "upload":
            output_dir = os.path.join(temp_path, "output")
            os.makedirs(output_dir, exist_ok=True)

        return temp_path

    def generate_task_id(self):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choices(characters, k=8))

    def init_uploader(self, file_path, mode):
        task_id = self.generate_task_id()
        temp = self._create_temp_dir(task_id, "upload")
        progress = init_progress_json(temp, "u")
        info = {"id": task_id, "file": file_path, "thread": None, "progress": progress, "temp": temp}
        if mode == "info":
            info["mode"] = "info"
            self.uploader_list.append(info)
        else:
            info["mode"] = ""
            self.uploader_list.append(info)

        return task_id

    def start_upload_task(self, task_id):
        for uploader in self.uploader_list:
            if uploader["id"] == task_id:
                upload_thread = threading.Thread(
                    target=self.upload_task,
                    args=(task_id, uploader["file"], uploader["progress"], uploader["temp"], uploader["mode"], )
                )
                upload_thread.start()
                uploader["thread"] = upload_thread
                break

    def upload_task(self, task_id, file_path, progress, temp, mode):

        if mode == "info":
            encoder = encode.QRender(task_id, file_path, temp, self.setting, progress, "info")
        else:
            encoder = encode.QRender(task_id, file_path, temp, self.setting, progress, "")
        encoder.execute()
        video_path = encoder.result_path()

        web_uploader = BiliUploader(video_path, temp,progress, mode, self.cookie_info, self.setting)
        web_uploader.upload_video()

    def upload_file(self, file_path, mode):
        task_id = self.init_uploader(file_path, mode)
        self.start_upload_task(task_id)

    def init_downloader(self, url, out, file_name):

        task_id = self.generate_task_id()
        temp = self._create_temp_dir(task_id, "upload")
        progress = init_progress_json(temp, "d")
        self.downloader_list.append({"id": task_id, "url": url, "out": out, "thread": None, "temp":temp, "progress": progress, "file_name": file_name})
        return task_id

    def download_task(self, url, task_id, out, progress, file_name):
        temp = self._create_temp_dir(task_id, "download")
        downloader = BiliBiliDownloader(url, self.aria2, self.setting)
        downloader.start_download(temp, progress)

        while True:
            status = downloader.get_status()

            if status["status"] == "complete":
                break
            time.sleep(0.1)

        decoder = decode.QRDecoder(task_id, status["dir"],out,"f9.jpg", temp, progress, self.setting)
        decoder.execute()

    def start_download_task(self, task_id):
        for downloader in self.downloader_list:
            if downloader["id"] == task_id:
                download_thread = threading.Thread(
                    target=self.download_task,
                    args=(downloader["url"], task_id, downloader["out"], downloader["progress"], )
                )
                download_thread.start()
                downloader["thread"] = download_thread
                break

    def download_file(self, video_url, out_path, file_name):
        task_id = self.init_downloader(video_url, out_path, file_name)
        self.start_download_task(task_id)

