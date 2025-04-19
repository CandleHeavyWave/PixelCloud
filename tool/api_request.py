from http.cookiejar import LWPCookieJar
from typing import Dict, Optional, Union

import requests
from fake_useragent import UserAgent


class ApiRequest:
    DEFAULT_HEADERS = {
        "User-Agent": UserAgent().random,
        "Referer": "https://www.bilibili.com/"
    }

    def __init__(self, setting):
        self.setting = setting
        self._load_cookies()

    def _load_cookies(self):

        n = self.setting.read_now_cookie()
        cookie_file = f"cookies/{str(n)}.cookie"
        self.session = requests.Session()
        self.session.cookies = LWPCookieJar(filename=cookie_file)
        self.session.cookies.load(ignore_discard=True)

    def get_response(self, method: str, url: str, params: Optional[Dict] = None, data: Optional[Union[Dict, bytes, list]] = None, is_json: bool = False, headers=None, session=None):
        """
        通用 API 请求方法。

        :param method: HTTP 方法（GET/POST/PUT）
        :param url: 请求 URL
        :param params: URL 参数
        :param data: 请求体数据
        :param headers: 自定义请求头
        :param is_json: 是否发送 JSON 数据
        :param session: 自定义对话
        :return: 响应字典
        """

        if headers is None:
            headers = self.DEFAULT_HEADERS
        else:
            headers = {**self.DEFAULT_HEADERS, **(headers or {})}

        if session is None:
            pass
        else:
            self.session = session

        if method.upper() == 'GET':
            self.response = self.session.get(url, params=params, headers=headers)
        elif method.upper() == 'POST':
            if is_json:
                self.response = self.session.post(url, json=data, params=params, headers=headers)
            else:
                self.response = self.session.post(url, data=data, params=params, headers=headers)
        elif method.upper() == 'PUT':
            self.response = self.session.put(url, data=data, params=params, headers=headers)

        self.response.raise_for_status()

        try:
            return self.response.json()
        except requests.exceptions.JSONDecodeError:
            self.response.encoding = "utf-8"
            return self.response
