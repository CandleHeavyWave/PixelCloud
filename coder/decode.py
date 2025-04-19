import base64
import os
import shutil
import subprocess
import time
from multiprocessing import Process, Queue, Manager, Value
from queue import Empty

import cv2
from natsort import natsorted
from pyzbar.pyzbar import decode

from tool.progress_json import write_progress_json


class QRDecoder:
    def __init__(self, task_id, video_path, out_path, file_name, temp_dir,progress,  settings):
        self.task_id = task_id
        self.video_path = video_path
        self.temp_dir = temp_dir
        self.file_name = file_name
        self.progress = progress

        self.out_path = out_path

    def _fetch_frames(self):

        cmd = [
            "ffmpeg",
            "-i", self.video_path,
            "-vsync", "0",
            f"{self.temp_dir}/img/%d.png"
        ]

        subprocess.run(cmd, check=True)

    def _decode_img(self, img_path):
        image = cv2.imread(f"{self.temp_dir}/img/{img_path}")
        decoded_objects = decode(image)

        for obj in decoded_objects:
            return base64.b64decode(obj.data)


    def _worker(self, imgs_queue, done_counter, completed_indexes, data_dic):

        while True:
            try:
                img = imgs_queue.get(timeout=0.001)

                data = self._decode_img(img["img"])
                data_dic[img["index"]] = data
                with done_counter.get_lock():
                    done_counter.value += 1
                completed_indexes.append(img["index"])

            except Empty:
                break

    def execute(self):

        self._fetch_frames()

        imgs = os.listdir(f"{self.temp_dir}/img")
        imgs = natsorted(imgs, key=lambda x: int(x.split('.')[0]))
        self.total_imgs = len(imgs)

        imgs_queue = Queue()
        i = 1
        for img in imgs:
            imgs_queue.put({"index":i, "img":img})
            i += 1
        manager = Manager()
        self.done_counter = Value('i', 0)
        self.completed_indexes = manager.list()
        data_list = manager.dict()

        processes = []
        for _ in range(os.cpu_count()):
            p = Process(target=self._worker, args=(imgs_queue, self.done_counter, self.completed_indexes, data_list))
            processes.append(p)
            p.start()

        self._update_progress()

        sorted_indices = sorted(data_list.keys())
        binary_data = bytearray()
        for index in sorted_indices:
            binary_data.extend(data_list[index])
        with open(f"{self.out_path}/{self.file_name}", "wb") as f:
            f.write(binary_data)
        self.progress["decode"][1]["is_wirte_file"] = True

    def _update_progress(self):
        while True:
            with self.done_counter.get_lock():
                current = self.done_counter.value

            print(current, self.total_imgs)
            self.progress["decode"][0]["percent"] = (current / self.total_imgs) * 100
            self.progress["decode"][0]["completed_img_indexes"] = list(self.completed_indexes)
            write_progress_json(self.temp_dir, self.progress)

            if current / self.total_imgs * 100 == 100.0:
                self.progress["decode"][0]["is_decode"] = True
                break
            time.sleep(0.1)


    def clean_up(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
