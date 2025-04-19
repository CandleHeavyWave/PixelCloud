import json
import os
from typing import Dict

import qrcode


class Setting:
    def __init__(self):
        self.set_json = {}
        self.init_json()

    def init_json(self):
        if not os.path.exists("setting.json"):
            with open("setting.json", "w") as f:
                self.set_json = {"login": {"now_cookie": ""},
                                 "encode": {"box_size": 10,
                                           "boder": 0,
                                           "error_correction": qrcode.constants.ERROR_CORRECT_L,
                                           "chuck_size": 1024,
                                           "qr_version": 20,
                                           "fps": 5},
                                 "aria2": {"sever_port": None}}
                json.dump(self.set_json, f)
                self.read_json()
        else:
            self.read_json()

    def read_json(self):
        with open("setting.json", "r") as f:
            self.json = f.read()
            self.set_json = json.loads(self.json)

    def writer_json(self):
        with open("setting.json", "w") as f:
            json.dump(self.set_json, f)

    def read_now_cookie(self) -> str:
        number = self.set_json["login"]["now_cookie"]
        return number

    def set_now_cookie(self, number):
        self.set_json["login"]["now_cookie"] = number
        self.writer_json()

    def set_aria2_port(self, port):
        self.set_json["aria2"]["sever_port"] = port
        self.writer_json()

    def read_aria_2port(self) -> str:
        port = self.set_json["aria2"]["sever_port"]
        return port

    def read_encoder_setting(self) -> Dict:
        box_size = self.set_json["encode"]["box_size"]
        boder = self.set_json["encode"]["boder"]
        error_correction = self.set_json["encode"]["error_correction"]
        chuck_size = self.set_json["encode"]["chuck_size"]
        fps = self.set_json["encode"]["fps"]
        qr_version = self.set_json["encode"]["qr_version"]
        return \
        {
            "box_size": box_size,
            "boder": boder,
            "error_correction": error_correction,
            "chuck_size": chuck_size,
            "qr_version": qr_version,
            "fps": fps
        }
