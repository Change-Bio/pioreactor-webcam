# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import click
from pioreactor.background_jobs.base import BackgroundJobWithDodgingContrib
from pioreactor.config import config
from pioreactor.whoami import get_latest_experiment_name
from pioreactor.whoami import get_unit_name

__plugin_summary__ = "Webcam recorder plugin for continuous video recording with HLS streaming"
__plugin_version__ = "1.0.0"
__plugin_name__ = "pioreactor_webcam_recorder"
__plugin_author__ = "Pioreactor Community"
__plugin_homepage__ = "https://github.com/pioreactor/pioreactor-webcam"


class WebcamRecorder(BackgroundJobWithDodgingContrib):
    published_settings = {
        "is_recording": {"datatype": "boolean", "settable": True},
    }

    job_name = "webcam_recorder"

    def __init__(self, unit: str, experiment: str) -> None:
        super().__init__(unit=unit, experiment=experiment, plugin_name="webcam_recorder")
        
        self.save_dir = Path(config.get("webcam_recorder.config", "save_dir", fallback="/home/pioreactor/data/camera"))
        self.hls_dir = Path(config.get("webcam_recorder.config", "hls_dir", fallback="/var/www/pioreactorui/data"))
        self.segment_duration = config.getint("webcam_recorder.config", "segment_duration_minutes", fallback=15)
        self.width = config.getint("webcam_recorder.config", "width", fallback=1920)
        self.height = config.getint("webcam_recorder.config", "height", fallback=1080)
        self.framerate = config.getint("webcam_recorder.config", "framerate", fallback=30)
        self.vflip = config.getboolean("webcam_recorder.config", "vflip", fallback=True)
        
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.hls_dir.mkdir(parents=True, exist_ok=True)
        
        self.recording_process = None
        self.recording_thread = None
        self.is_recording = False

    def on_init_to_ready(self) -> None:
        super().on_init_to_ready()
        self.logger.info("Webcam recorder initialized and ready")
        # Start with recording disabled - can be enabled via UI or API

    def set_is_recording(self, value: bool) -> None:
        if value == self.is_recording:
            return

        if value:
            self.start_recording()
        else:
            self.stop_recording()
        
        self.is_recording = value

    def start_recording(self) -> None:
        if self.recording_thread and self.recording_thread.is_alive():
            return
            
        self.logger.info("Starting webcam recording")
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()

    def stop_recording(self) -> None:
        self.logger.info("Stopping webcam recording")
        if self.recording_process:
            self.recording_process.terminate()
            try:
                self.recording_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.recording_process.kill()
                self.recording_process.wait()
            self.recording_process = None

    def _clean_old_hls_segments(self) -> None:
        try:
            for file in self.hls_dir.glob("webcam*.ts"):
                file.unlink()
            for file in self.hls_dir.glob("webcam.m3u8"):
                file.unlink()
        except Exception as e:
            self.logger.warning(f"Failed to clean old HLS segments: {e}")

    def _recording_loop(self) -> None:
        while self.is_recording:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                output_tmp = self.save_dir / f"raw_{timestamp}.h264.tmp"
                output_final = self.save_dir / f"raw_{timestamp}.h264"
                
                self._clean_old_hls_segments()
                
                segment_duration_ms = self.segment_duration * 60 * 1000
                
                rpicam_cmd = [
                    "rpicam-vid",
                    "-t", str(segment_duration_ms),
                    "--width", str(self.width),
                    "--height", str(self.height),
                    "--framerate", str(self.framerate),
                    "--nopreview",
                    "--codec", "h264",
                    "--profile", "high",
                    "--inline",
                    "--level", "4.2",
                    "-o", "-"
                ]
                
                if self.vflip:
                    rpicam_cmd.insert(-2, "--vflip")
                
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-nostdin",
                    "-f", "h264",
                    "-i", "-",
                    "-c", "copy",
                    "-f", "hls",
                    "-hls_time", "2",
                    "-hls_list_size", "5",
                    "-hls_flags", "delete_segments",
                    str(self.hls_dir / "webcam.m3u8")
                ]
                
                with open(output_tmp, 'wb') as f:
                    rpicam_process = subprocess.Popen(rpicam_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=rpicam_process.stdout, stderr=subprocess.PIPE)
                    
                    self.recording_process = rpicam_process
                    
                    while True:
                        chunk = rpicam_process.stdout.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        if not self.is_recording:
                            break
                    
                    rpicam_process.wait()
                    ffmpeg_process.wait()
                    
                    if rpicam_process.returncode == 0:
                        output_tmp.rename(output_final)
                        self.logger.info(f"Successfully recorded segment: {output_final}")
                    else:
                        self.logger.error(f"Recording failed at {timestamp}")
                        with open("/tmp/record_camera_errors.log", "a") as error_log:
                            error_log.write(f"Recording failed at {timestamp}\n")
                        if output_tmp.exists():
                            output_tmp.unlink()
                            
            except Exception as e:
                self.logger.error(f"Error in recording loop: {e}")
                time.sleep(5)

    def on_disconnected(self) -> None:
        super().on_disconnected()
        self.stop_recording()


@click.command(name="webcam_recorder")
def click_webcam_recorder() -> None:
    """
    Start the webcam recorder
    """
    job = WebcamRecorder(
        unit=get_unit_name(),
        experiment=get_latest_experiment_name(),
    )
    job.block_until_disconnected()


if __name__ == "__main__":
    click_webcam_recorder()
