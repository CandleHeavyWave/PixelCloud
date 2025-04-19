import base64
import os
import shutil
import subprocess
import time
from multiprocessing import Process, Queue, Manager, Value, cpu_count
from queue import Empty

import qrcode

from tool.progress_json import write_progress_json


class QRender:
    def __init__(self, task_id, file_path, temp_dir, settings, progress, mode):
        self.task_id = task_id
        self.progress = progress
        self.file_path = file_path
        self.mode = mode
        self.temp_dir = temp_dir
        self.settings = settings.read_encoder_setting()

    def _read_file_chunks(self):
        with open(self.file_path, 'rb') as f:
            chunk_size = self.settings["chuck_size"]
            index = 0
            while True:
                chunk = f.read(chunk_size)

                if not chunk:
                    break
                yield {"index": index, "data": chunk}
                index += 1

    def _generate_chunk_qr(self, chunk_data, index):

        qr = qrcode.QRCode(
            error_correction=self.settings["error_correction"],
            box_size=self.settings["box_size"],
            border=self.settings["boder"],
        )
        qr.add_data(base64.b64encode(chunk_data).decode('utf-8'))
        qr.make(fit=False)
        img = qr.make_image(fill_color="black", back_color="white")
        self.qr_size["size"] = img.size
        img.save(os.path.join(self.temp_dir, "img", f"{index}.png"))

    def _worker(self, chunk_queue, done_counter, completed_indexes):

        while True:
            try:
                chunk = chunk_queue.get()
            except Empty:
                break

            self._generate_chunk_qr(chunk["data"], chunk["index"])

            with done_counter.get_lock():
                done_counter.value += 1
            completed_indexes.append(chunk["index"])

    def _composite_video(self):

        fps = self.settings["fps"]
        os.path.join(self.temp_dir, "output", f"{self.task_id}.mp4")

        min_duration = 1.0
        if self.total_chunks / fps < min_duration:
            fps = max(1, int(self.total_chunks / min_duration))

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-pattern_type", "sequence",
            "-i", f"{self.temp_dir}/img/%d.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            f"{self.temp_dir}/output/{self.task_id}.mp4"
        ]

        subprocess.run(cmd, check=True, capture_output=True)


    def _update_progress(self):
        while True:
            with self.done_counter.get_lock():
                current = self.done_counter.value

            self.progress["encode"][0]["percent"] = current / self.total_chunks * 100
            self.progress["encode"][0]["completed_chucks_indexes"] = list(self.completed_indexes)
            write_progress_json(self.temp_dir, self.progress)

            if current / self.total_chunks * 100 == 100.0:
                break
            time.sleep(0.1)


    def execute(self):

        manager = Manager()
        chunk_queue = Queue()
        self.done_counter = Value('i', 0)
        self.completed_indexes = manager.list()
        self.qr_size = manager.dict()
        self.chunks = list(self._read_file_chunks())
        self.total_chunks = len(self.chunks)

        for i in self.chunks:
            chunk_queue.put(i)

        processes = []
        for _ in range(cpu_count()):
            p = Process(target=self._worker,
                        args=(chunk_queue, self.done_counter, self.completed_indexes))
            p.start()
            processes.append(p)

        self._update_progress()
        self.progress["encode"][0]["is_encode"] = True
        write_progress_json(self.temp_dir, self.progress)

        self._composite_video()
        self.progress["encode"][1]["is_composite_video"] = True
        write_progress_json(self.temp_dir, self.progress)

    def clean_up(self):

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def result_path(self):
        return os.path.join(self.temp_dir, "output", f"{self.task_id}.mp4")