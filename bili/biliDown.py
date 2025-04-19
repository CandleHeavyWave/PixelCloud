import re

from tool.api_request import ApiRequest


class BiliBiliDownloader:

    def __init__(self, url, aria2, setting):
        self.url = url
        self.setting = setting
        self.aria2 = aria2
        self.init_downloader()
        self._api_request = ApiRequest(self.setting)

    def get_video_address(self):
        cid = self.get_cid()
        params = {
            "bvid": self.vid,
            "cid": cid,
            "high_quality": 1
        }

        response = self._api_request.get_response("GET", "https://api.bilibili.com/x/player/wbi/playurl?", params)
        return response["data"]["durl"][0]["url"]

    def get_cid(self):
        params = {
            "bvid": self.vid
        }

        response = self._api_request.get_response("GET", "https://api.bilibili.com/x/web-interface/view?", params)
        return response["data"]["cid"]

    def init_downloader(self):
        self.vid = re.findall("https://www.bilibili.com/video/(.*?)/", self.url)[0]

    def start_download(self, output, progress):

        video_url = self.get_video_address()
        header = [
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer: https://www.bilibili.com/"
        ]
        self.gid = self.aria2.startDownloading(video_url, output, header, progress)

    def get_status(self):
        return self.aria2.getStatus(self.gid)
