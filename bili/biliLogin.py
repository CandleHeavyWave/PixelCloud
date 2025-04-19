import os
import time
from http.cookiejar import LWPCookieJar

import requests
from qrcode import QRCode

from tool import api_request


class LoginStatusCode:
    Success = 0
    NotScanned = 1
    ScannedNotConfirmed = 2
    Expired = 3

class BiliBiliLogin:
    def __init__(self, setting):
        self.setting = setting
        self.cookie_dir = "cookies"
        self._api_request = api_request.ApiRequest(setting)
        self.load_cookie_files()

    def load_cookie_files(self):

        if not os.path.exists(self.cookie_dir):
            os.makedirs(self.cookie_dir)

        self.cookie_files = [
            os.path.join(self.cookie_dir, f)
            for f in os.listdir(self.cookie_dir)
            if f.endswith(".cookie")
        ]
        self.cookie_files.sort()

    def init_session(self, number: str):
        cookie_file = f"{self.cookie_dir}/{number}.cookie"
        session = requests.Session()
        session.cookies = LWPCookieJar(filename=cookie_file)

        if not os.path.exists(cookie_file):
            session.cookies.save(ignore_discard=True)

        session.cookies.load(ignore_discard=True)
        return session

    def get_cookies_info(self) -> list:
        cookies_list = []
        for i, cookie_file in enumerate(self.cookie_files):

            mid, bili_jct = None, None
            session = self.init_session(str(i))

            for c in session.cookies:
                if c.name == 'DedeUserID':
                    mid = c.value
                if c.name == 'bili_jct':
                    bili_jct = c.value

            response = self._api_request.get_response(
                "GET",
                "https://api.bilibili.com/x/web-interface/nav",
                session=session
            )

            cookies_list.append({
                "number": i,
                "mid": mid,
                "bili_jct": bili_jct,
                "face_url": response['data']['face'],
                "uname": response['data']['uname'],
                "web": "哔哩哔哩",
                "cookie_file": cookie_file
            })

        return cookies_list

    def get_qrcode_img(self):
        params = {"source": "source=main-fe-header"}
        response = self._api_request.get_response(
            "GET",
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
            params=params
        )

        qrcode_key = response['data']['qrcode_key']
        qr = QRCode()
        qr.add_data(response['data']['url'])
        img = qr.make_image()
        return img, qrcode_key

    def pollQrcode(self, qrcode_key: str, number: str):
        session = self.init_session(number)
        while True:
            params = {"qrcode_key": qrcode_key, "source": "source=main-fe-header"}
            response = self._api_request.get_response(
                "GET",
                f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                params=params
            )

            data = response.get('data', {})
            code = data.get('coder', None)
            if code == 0:
                session.get(data.get('url'), headers=self._api_request.DEFAULT_HEADERS)
                session.cookies.save(ignore_discard=True)
                return LoginStatusCode.Success
            elif code == 86090:
                return LoginStatusCode.NotScanned
            elif code == 86101:
                return LoginStatusCode.ScannedNotConfirmed
            elif code == 86038:
                return LoginStatusCode.Expired

            time.sleep(1)

    def login(self):
        c_list = self.get_cookies_info()
        new_number = str(len(c_list) + 1)
        self.init_session(new_number)
        img, qrcode_key = self.get_qrcode_img()
        return img, qrcode_key






