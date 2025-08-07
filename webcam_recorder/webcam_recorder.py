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
        # Initialize attributes first to prevent AttributeError in cleanup methods
        self.camera_process = None
        self.ffmpeg_process = None
        self.streaming_thread = None
        self.current_file_handle = None
        
        super().__init__(unit=unit, experiment=experiment, plugin_name="webcam_recorder")
        
        # Set this after super().__init__() to avoid AttributeError
        self.is_recording = False
        
        self.save_dir = Path(config.get("webcam_recorder.config", "save_dir", fallback="/home/pioreactor/data/camera"))
        self.hls_dir = Path(config.get("webcam_recorder.config", "hls_dir", fallback="/var/www/pioreactorui/data"))
        self.segment_duration = config.getint("webcam_recorder.config", "segment_duration_minutes", fallback=15)
        self.width = config.getint("webcam_recorder.config", "width", fallback=1920)
        self.height = config.getint("webcam_recorder.config", "height", fallback=1080)
        self.framerate = config.getint("webcam_recorder.config", "framerate", fallback=30)
        self.vflip = config.getboolean("webcam_recorder.config", "vflip", fallback=True)
        
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.hls_dir.mkdir(parents=True, exist_ok=True)

    def on_init_to_ready(self) -> None:
        super().on_init_to_ready()
        self.logger.info("Webcam recorder initialized and ready")
        # Start camera streaming immediately when job starts
        self.start_camera_streaming()
        # Storage recording remains disabled until explicitly enabled

    def set_is_recording(self, value: bool) -> None:
        if value == self.is_recording:
            return

        self.is_recording = value
        self.logger.info(f"Recording {'enabled' if value else 'disabled'}")

    def start_camera_streaming(self) -> None:
        if self.streaming_thread and self.streaming_thread.is_alive():
            return
            
        self.logger.info("Starting camera streaming")
        self.streaming_thread = threading.Thread(target=self._camera_streaming_loop, daemon=True)
        self.streaming_thread.start()

    def stop_camera_streaming(self) -> None:
        self.logger.info("Stopping camera streaming")
        if self.camera_process:
            self.camera_process.terminate()
            try:
                self.camera_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.camera_process.kill()
                self.camera_process.wait()
            self.camera_process = None
        
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
                self.ffmpeg_process.wait()
            self.ffmpeg_process = None
        
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None

    def _clean_old_hls_segments(self) -> None:
        try:
            for file in self.hls_dir.glob("webcam*.ts"):
                file.unlink()
            for file in self.hls_dir.glob("webcam.m3u8"):
                file.unlink()
        except Exception as e:
            self.logger.warning(f"Failed to clean old HLS segments: {e}")

    def _camera_streaming_loop(self) -> None:
        """Single camera process that streams to HLS and optionally saves to file"""
        while self.state != "disconnected":
            try:
                self._clean_old_hls_segments()
                
                rpicam_cmd = [
                    "rpicam-vid",
                    "-t", "0",  # Continuous streaming
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
                
                self.camera_process = subprocess.Popen(rpicam_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                
                current_segment_start = None
                current_file_path = None
                
                while True:
                    chunk = self.camera_process.stdout.read(8192)
                    if not chunk:
                        break
                    
                    # Always send to HLS stream
                    try:
                        self.ffmpeg_process.stdin.write(chunk)
                        self.ffmpeg_process.stdin.flush()
                    except (BrokenPipeError, OSError):
                        self.logger.warning("HLS stream disconnected")
                        break
                    
                    # Handle file recording based on is_recording flag
                    if self.is_recording:
                        # Start new segment if needed
                        if (current_segment_start is None or 
                            (datetime.now() - current_segment_start).total_seconds() >= self.segment_duration * 60):
                            
                            # Close previous file if open
                            if self.current_file_handle:
                                self.current_file_handle.close()
                                if current_file_path and current_file_path.with_suffix('.tmp').exists():
                                    current_file_path.with_suffix('.tmp').rename(current_file_path)
                                    self.logger.info(f"Completed recording segment: {current_file_path}")
                            
                            # Start new segment
                            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                            current_file_path = self.save_dir / f"raw_{timestamp}.h264"
                            temp_file_path = current_file_path.with_suffix('.tmp')
                            
                            self.current_file_handle = open(temp_file_path, 'wb')
                            current_segment_start = datetime.now()
                        
                        # Write to current file
                        if self.current_file_handle:
                            self.current_file_handle.write(chunk)
                            self.current_file_handle.flush()
                    else:
                        # Recording disabled - close any open file
                        if self.current_file_handle:
                            self.current_file_handle.close()
                            self.current_file_handle = None
                            if current_file_path and current_file_path.with_suffix('.tmp').exists():
                                current_file_path.with_suffix('.tmp').rename(current_file_path)
                                self.logger.info(f"Completed recording segment: {current_file_path}")
                            current_segment_start = None
                            current_file_path = None
                
                # Clean up processes
                self.camera_process.wait()
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait()
                
                if self.camera_process.returncode != 0 and self.state != "disconnected":
                    self.logger.error("Camera streaming failed, restarting in 5 seconds")
                    time.sleep(5)
                            
            except Exception as e:
                self.logger.error(f"Error in camera streaming loop: {e}")
                time.sleep(5)

    def on_disconnected(self) -> None:
        super().on_disconnected()
        self.stop_camera_streaming()


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
