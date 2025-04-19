import time
import urllib.parse
from functools import reduce
from hashlib import md5

import requests


class WbiSigner:
    _MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]

    def __init__(self, refresh_interval: int = 1800):
        self.img_key = ''
        self.sub_key = ''
        self.refresh_interval = refresh_interval  # 默认30分钟刷新一次
        self.last_refresh = 0
        self._refresh_keys()

    def _refresh_keys(self):
        """获取并更新最新的img_key和sub_key"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://www.bilibili.com/'
        }
        try:
            resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers)
            resp.raise_for_status()
            data = resp.json().get('data', {})
            wbi_img = data.get('wbi_img', {})
            self.img_key = wbi_img.get('img_url', '').rsplit('/', 1)[-1].split('.')[0]
            self.sub_key = wbi_img.get('sub_url', '').rsplit('/', 1)[-1].split('.')[0]
            self.last_refresh = time.time()
        except (requests.RequestException, KeyError, IndexError) as e:
            raise RuntimeError("Failed to refresh WBI keys") from e

    def _needs_refresh(self):
        """检查是否需要刷新keys"""
        return time.time() - self.last_refresh > self.refresh_interval

    def _get_mixin_key(self, orig: str):
        """生成混合密钥"""
        return reduce(lambda s, i: s + orig[i], self._MIXIN_KEY_ENC_TAB, '')[:32]

    def sign(self, params: dict):
        """对参数进行WBI签名"""
        if self._needs_refresh():
            self._refresh_keys()

        # 准备基础参数
        params = params.copy()
        params['wts'] = int(time.time())

        # 排序并过滤参数
        sorted_params = dict(sorted(params.items()))
        filtered_params = {
            k: ''.join(filter(lambda c: c not in "!'()*", str(v)))
            for k, v in sorted_params.items()
        }

        query = urllib.parse.urlencode(filtered_params)
        mixin_key = self._get_mixin_key(self.img_key + self.sub_key)
        w_rid = md5((query + mixin_key).encode()).hexdigest()

        # 返回签名后的参数
        return {**filtered_params, 'w_rid': w_rid}

