import multiprocessing
import os
import random
import socket
import subprocess
import time
from urllib.parse import urlparse

from aria2p import API, Client

from tool.api_request import ApiRequest
from tool.progress_json import write_progress_json


class Aria2:
    def __init__(self, setting):
        self.setting = setting
        self.port = self.get_random_port()
        self._api_resquet = ApiRequest(self.setting)

    def start_aria2_sever(self):

        self.config_dir = os.path.abspath("aria2c.conf")

        with open(self.config_dir, "w") as f:
            f.write("enable-rpc=true\n"
                    "rpc-listen-all=false\n"
                    f"rpc-listen-port={self.port}\n"
                    "log=NUL\n"
                    "log-level=warn\n")

        cmd = [
            "aria2c",
            f"--conf-path={self.config_dir}",
            "--daemon=true"
        ]

        self.aria2_process = multiprocessing.Process(
            target=subprocess.run,
            args=(cmd, )
        )
        self.aria2_process.start()

    def stop_aria2_sever(self):
        self.aria2_process.terminate()

    def extract_url_filename(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        filename = path.split('/')[-1]
        return filename

    def is_portinuse(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def get_random_port(self, min_port=1024, max_port=65535):
        while True:
            port = random.randint(min_port, max_port)
            if not self.is_portinuse(port):
                return port

    def start_downloading(self, url, output, header, progress):

        filename = self.extract_url_filename(url)
        aria2_client = Client(
            host="http://localhost",
            port=self.port,
        )
        aria2 = API(aria2_client)

        downloader = aria2.add_uris([url], options={"dir": output, "out": filename, "header": header, "split": "8"})
        self._update_progress(downloader.gid, progress, output)
        return downloader.gid

    def _update_progress(self, gid, progress, temp):
        while True:
            status = self.get_status(gid)
            progress["download"][0]["percent"] = status["progress"]
            progress["download"][0]["download_speed"] = status["download_speed"]
            progress["download"][0]["total_length"] = status["total_length"]

            if status["status"] == "complete":
                progress["download"][0]["is_download"] = True
                break

            write_progress_json(temp, progress)
            time.sleep(0.1)


    def get_status(self, gid):
        payload = {
            "jsonrpc": "2.0",
            "method": "aria2.tellStatus",
            "id": "1",
            "params": [gid]
        }
        headers = {"Content-Type": "application/json"}
        result = self._api_resquet.get_response("POST", f"http://localhost:{self.port}/jsonrpc", data=payload,
                                               headers=headers, is_json=True)

        total_length = result["result"]["totalLength"]
        completed_length = result["result"]["completedLength"]

        if total_length == "0":
            progress = 0.0
        else:
            progress = float(completed_length) / float(total_length) * 100

        files = result["result"]["files"]
        file_paths = [file["path"] for file in files]

        status = {
            "gid": result["result"]["gid"],
            "status": result["result"]["status"],
            "progress": progress,
            "download_speed": result["result"]["downloadSpeed"],
            "upload_speed": result["result"]["uploadSpeed"],
            "total_length": total_length,
            "completed_length": completed_length,
            "files": file_paths,
            "dir": result["result"]["files"][0]["path"]
        }
        return status
