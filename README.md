## Pioreactor Webcam Recorder Plugin

A Pioreactor plugin for continuous webcam recording with HLS streaming support. This plugin enables automated video recording of your bioreactor experiments with configurable recording parameters and real-time streaming capabilities.

## Installation

Install from the Pioreactor plugins web interface or the command line:

```
pio install-plugin pioreactor-webcam    # to install directly on the Pioreactor

# OR, on the leader's command line:

pios install-plugin pioreactor-webcam # to install on all Pioreactors in a cluster
```

Or install through the web interface (_Plugins_ tab). This will install the plugin on all Pioreactors within the cluster.

### Raspberry Pi Camera Setup

To get the camera working on a Raspberry Pi running the Pioreactor image, you may need to:

1. Enable camera autodetection by editing `/boot/config.txt` (add or uncomment `camera_auto_detect=1`)
2. Update to the latest firmware:
```bash
sudo apt update
sudo apt full-upgrade
```
3. Reboot the Pi after making these changes

### Configuration

You can customize the webcam recorder settings by adding the following to your Pioreactor configuration:

```
[webcam_recorder.config]
save_dir=/home/pioreactor/data/camera
hls_dir=/var/www/pioreactorui/data
segment_duration_minutes=15
width=1920
height=1080
framerate=30
vflip=true
```

## Usage

#### Through the command line:
```
pio run webcam_recorder
```

#### Through the UI:

Under _Manage_, there will be a new _Activities_ option called _Webcam Recorder_. You can start/stop recording using the `is_recording` setting.

### Features

- **Continuous Recording**: Records video in configurable segments (default 15 minutes)
- **HLS Streaming**: Provides real-time streaming via HTTP Live Streaming
- **Configurable Parameters**: Adjustable resolution, framerate, and recording duration
- **Automatic File Management**: Handles file naming with timestamps and cleanup
- **Raspberry Pi Camera Support**: Uses `rpicam-vid` for efficient video capture
- **Background Job**: Integrates with Pioreactor's job system with dodging support

### Important Notes

- **Viewing the Stream**: If you're connected to the Tailscale network, you can view the live camera stream using VLC or any HLS-compatible player by opening: `http://your-pioreactor-ip/data/webcam.m3u8`. No UI changes are required for basic streaming functionality.
- **Disk Space Warning**: Video recording uses significant disk space. Monitor your storage regularly to prevent the disk from filling up. Consider implementing automatic cleanup of old recordings or using external storage for long-term archival 

## Plugin documentation

Documentation for plugins can be found on the [Pioreactor docs](https://docs.pioreactor.com/developer-guide/intro-plugins).
