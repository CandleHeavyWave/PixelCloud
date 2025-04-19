import base64
import os
import time
from typing import Dict

import cv2

from tool.api_request import ApiRequest
from tool.progress_json import write_progress_json


class BiliUploader:

    def __init__(self, video_path: str, temp: str, progress: Dict, mode: str, cookie_info: list, setting):
        self.video_path = video_path
        self.temp = temp
        self.progress = progress
        self.mode = mode
        self.setting = setting

        self._init_video_metadata()
        self._api_request = ApiRequest(self.setting)

        self.bili_jct = cookie_info[self.setting.read_now_cookie()]["bili_jct"]

    def _init_video_metadata(self):
        self.video_name = os.path.basename(self.video_path)
        self.file_size = os.path.getsize(self.video_path)

    def get_video_types(self) -> str:
        data = {
            "filename": self.video_name
        }

        params = {
            'csrf': self.bili_jct,
            'cover': self.cover_base64
        }

        response = self._api_request.get_response(
            'POST',
            'https://member.bilibili.com/x/vupre/web/archive/types/predict',
            params=params,
            data=data,
        )

        v_type = response["data"][0]["id"]
        return v_type

    def upload_cover(self) -> str:

        params = {'ts': int(time.time() * 1000)}
        frame = cv2.imread("black_cover.png")

        _, img_buffer = cv2.imencode(".png", frame)
        self.cover_base64 = f"data:image/jpeg;base64,{base64.b64encode(img_buffer).decode('utf-8')}"

        data = {
            'csrf': self.bili_jct,
            'cover': self.cover_base64
        }

        response = self._api_request.get_response(
            'POST',
            'https://member.bilibili.com/x/vu/web/cover/up',
            params=params,
            data=data,
        )
        self.cover_url = response.get('data', {}).get('url', '')
        self.progress["upload"][0]["is_upload_cover"] = True
        write_progress_json(self.temp, self.progress)

        return response.get('data', {}).get('url', '')

    def preupload_video(self):

        params = {
            'name': self.video_name,
            'r': 'upos',
            'profile': 'ugcfx/bup',
        }

        response = self._api_request.get_response(
            'GET',
            'https://member.bilibili.com/preupload',
            params=params,
        )

        self.upload_meta = {
            'auth': response.get('auth', ''),
            'chunk_size': response.get('chunk_size', 1 * 1024 * 1024),
            'endpoint': response.get('endpoint', ''),
            'upos_uri': response.get('upos_uri', ''),
            'biz_id': response.get('biz_id', '')
        }
        self.progress["upload"][1]["is_preupload_video"] = True
        write_progress_json(self.temp, self.progress)
        return self.upload_meta

    def init_upload_session(self) -> str:
        url = f"https:{self.upload_meta['endpoint']}/{self.upload_meta['upos_uri'].replace('upos://', '')}"
        params = {
            'uploads': '',
            'output': 'json',
            'profile': 'ugcfx/bup',
            'filesize': self.file_size,
            'partsize': self.upload_meta['chunk_size'],
            'biz_id': self.upload_meta['biz_id']
        }
        headers = {'X-Upos-Auth': self.upload_meta['auth']}

        response = self._api_request.get_response(
            'POST',
            url,
            params=params,
            headers=headers
        )

        self.upload_id = response.get('upload_id', '')
        self.progress["upload"][2]["is_init_upload_session"] = True
        write_progress_json(self.temp, self.progress)
        return self.upload_id

    def upload_chunks(self):
        """
        分块上传视频。
        """
        chunk_size = self.upload_meta['chunk_size']
        total_chunks = (self.file_size + chunk_size - 1) // chunk_size
        url = f"https:{self.upload_meta['endpoint']}/{self.upload_meta['upos_uri'].replace('upos://', '')}"

        with open(self.video_path, 'rb') as f:
            for chunk_num in range(total_chunks):
                start = chunk_num * chunk_size
                end = min(start + chunk_size, self.file_size)
                f.seek(start)
                data = f.read(end - start)

                params = {
                    'partNumber': chunk_num + 1,
                    'uploadId': self.upload_id,
                    'chunk': chunk_num,
                    'chunks': total_chunks,
                    'size': len(data),
                    'start': start,
                    'end': end,
                    'total': self.file_size
                }

                headers = {
                    'X-Upos-Auth': self.upload_meta['auth'],
                    'Content-Type': 'application/octet-stream'
                }

                response = self._api_request.get_response(
                    'PUT',
                    url,
                    params=params,
                    data=data,
                    headers=headers
                )
        self.progress["upload"][3]["is_upload_chunks"] = True
        write_progress_json(self.temp, self.progress)

    def complete_upload(self):

        total_chunks = (self.file_size + self.upload_meta['chunk_size'] - 1) // self.upload_meta['chunk_size']
        url = f"https:{self.upload_meta['endpoint']}/{self.upload_meta['upos_uri'].replace('upos://', '')}"
        params = {
            'output': 'json',
            'name': self.video_name,
            'profile': 'ugcfx/bup',
            'uploadId': self.upload_id,
            'biz_id': self.upload_meta['biz_id']
        }

        parts = [{"partNumber": i + 1, "eTag": "etag"} for i in range(total_chunks)]

        headers = {
            'X-Upos-Auth': self.upload_meta['auth'],
            'Content-Type': 'application/octet-stream'
        }

        response = self._api_request.get_response(
            'POST',
            url,
            params=params,
            data=parts,
            is_json=True,
            headers=headers
        )

        self.progress["upload"][4]["is_complete_upload"] = True
        write_progress_json(self.temp, self.progress)

        return response

    def upload_video(self):
        self.upload_cover()
        self.preupload_video()
        self.init_upload_session()
        self.upload_chunks()
        self.complete_upload()

        v_type = self.get_video_types()
        if self.mode == "info":
            desc = str({"id": os.path.basename(self.video_path), "mode": "data"})
        else:
            desc = str({"id": os.path.basename(self.video_path), "mode": "file"})
        metadata = {
            "title": desc,
            "desc": desc,
            "tag": "PixelCloud,像素网盘",
            "tid": v_type
        }
        self.submit_video(metadata)

    def submit_video(self, metadata: Dict = None) -> Dict:

        submit_data = {
            "videos": [
                {
                    "filename": self.upload_meta['upos_uri'].split('/')[-1].split(".")[0],
                    "title": os.path.basename(self.video_path),
                    "desc": "",
                    "cid": self.upload_meta['biz_id']
                }
            ],
            "cover": self.cover_url,
            "cover43": "",
            "title": metadata["title"],
            "copyright": 1,
            "tid": metadata["tid"],
            "tag": metadata["tag"],
            "desc_format_id": 9999,
            "desc": metadata["desc"],
            "recreate": -1,
            "interactive": 0,
            "act_reserve_create": 0,
            "no_disturbance": 0,
            "no_reprint": 1,
            "subtitle": {
                "open": 0,
                "lan": ""
            },
            "dolby": 0,
            "lossless_music": 0,
            "up_selection_reply": False,
            "up_close_reply": False,
            "up_close_danmu": False,
            "web_os": 3,
        }

        response = self._api_request.get_response(
            'POST',
            'https://member.bilibili.com/x/vu/web/add/v3',
            data=submit_data,
            params={"csrf": self.bili_jct},
            is_json=True,
        )
        self.progress["upload"][5]["is_submit_video"] = True
        write_progress_json(self.temp, self.progress)

        return response

    def is_only_self(self, b: bool, aid: str) -> Dict:
        url = "https://member.bilibili.com/x/vu/web/edit/visibility"
        data = {
            "aid": aid,
            "csrf": self.bili_jct
        }

        if b:
            data["is_only_self"] = 1
            response = self._api_request.get_response(
                'POST',
                url,
                params={"csrf": self.bili_jct},
                data=data,
                is_json=True,
            )
        else:
            data["is_only_self"] = 0
            response = self._api_request.get_response(
                'POST',
                url,
                params={"csrf": self.bili_jct},
                data=data,
                is_json=True,

            )

        return response




class BiliManuscriptEditor(BiliUploader):
    def __init__(self, bvid: str, video_path: str, temp: str, progress: Dict, setting):
        super().__init__(video_path, temp, progress, "", setting)
        self.bvid = bvid

    def get_old_information(self) -> Dict:
        params = {
            "bvid": self.bvid
        }

        response = self._api_request.get_response(
            'GET',
            'https://member.bilibili.com/x/vupre/web/archive/view',
            params=params,
        )

        self.aid = response["data"]["archive"]["aid"]
        self.cids = []
        for v in response["data"]["videos"]:
            self.cids.append(v["cid"])

        return response

    def submit_video(self, metadata: Dict = None) -> Dict:
        submit_data = {
            "videos": [
            ],
            "cover": self.cover_url,
            "cover43": "",
            "title": metadata["title"],
            "copyright": 1,
            "human_type2": 0,
            "tid": metadata["tid"],
            "tag": metadata["tag"],
            "desc": metadata["desc"],
            "dynamic": "",
            "recreate": -1,
            "interactive": 0,
            "aid": self.aid,
            "new_web_edit": 1,
            "handle_staff": False,
            "topic_grey": 1,
            "act_reserve_create": 0,
            "mission_id": 0,
            "is_only_self": 0,
            "watermark": {
                "state": 0
            },
            "no_reprint": 1,
            "subtitle": {
                "open": 0,
                "lan": ""
            },
            "is_360": -1,
            "dolby": 0,
            "lossless_music": 0,
            "web_os": 1,
            "csrf": self.bili_jct
        }

        for cid in self.cids:
            submit_data["videos"].append({
                    "filename": self.upload_meta['upos_uri'].split('/')[-1].split(".")[0],
                    "title": os.path.basename(self.video_path),
                    "desc": "",
                    "cid": cid
                })

        response = self._api_request.get_response(
            'POST',
            'https://member.bilibili.com/x/vu/web/edit',
            data=submit_data,
            params={"csrf": self.bili_jct},
            is_json=True,
        )
        self.progress["upload"][5]["is_submit_video"] = True
        write_progress_json(self.temp, self.progress)

        return response

    def upload_video(self):
        self.upload_cover()
        self.preupload_video()
        self.init_upload_session()
        self.upload_chunks()
        self.complete_upload()
        self.get_old_information()

        v_type = self.get_video_types()
        if self.mode == "info":
            desc = str({"id": os.path.basename(self.video_path), "mode": "data"})
        else:
            desc = str({"id": os.path.basename(self.video_path), "mode": "file"})

        metadata = {
            "title": desc,
            "desc": desc,
            "tag": "PixelCloud,像素网盘",
            "tid": v_type
        }
        self.submit_video(metadata)

