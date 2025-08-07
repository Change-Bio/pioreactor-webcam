# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the webcam recorder plugin for Pioreactor.

## Webcam Recorder Plugin Overview

This is a Pioreactor plugin that provides continuous HLS (HTTP Live Streaming) with optional video recording using the Raspberry Pi camera module. The plugin starts HLS streaming immediately when the job runs, and can optionally save video segments to storage when recording is enabled. This provides real-time streaming capabilities for monitoring bioreactor experiments with on-demand storage recording.

## Development Commands

### Plugin Installation and Testing
```bash
# Install plugin for development (from plugin directory)
pip install -e .

# Install plugin on Pioreactor directly
pio install-plugin webcam-recorder

# Install on all Pioreactors in cluster (run from leader)
pios install-plugin webcam-recorder

# Run plugin from command line
pio run webcam_recorder

# Test plugin functionality
python -m pytest webcam_recorder/test_webcam_recorder.py
```

### Package Building
```bash
# Build distribution package
python setup.py sdist bdist_wheel

# Check package contents
python -c "from setuptools import find_packages; print(find_packages())"
```

## Plugin Architecture

### Core Structure

```
webcam_recorder/                # Main plugin package directory
├── webcam_recorder.py          # Main plugin implementation (WebcamRecorder)
├── __init__.py                 # Package imports and entry points
├── additional_config.ini       # Plugin-specific configuration
├── additional_sql.sql          # Database schema for webcam data
├── post_install.sh            # Post-installation scripts
├── pre_uninstall.sh           # Pre-uninstall cleanup scripts
├── exportable_datasets/        # Data export configurations
│   └── exportable_dataset.yaml
└── ui/                         # Web UI integration files
    └── contrib/
        └── jobs/               # Job definition YAML files
            └── webcam_recorder.yaml
```

### Plugin Implementation Details

The WebcamRecorder class inherits from `BackgroundJobWithDodgingContrib` and implements:

- **Continuous HLS Streaming**: Uses `rpicam-vid` to capture H.264 video and streams via FFmpeg to generate HLS segments
- **Optional Storage Recording**: Conditionally saves raw H.264 video segments to disk when recording is enabled
- **Single Camera Process**: Uses one camera process that outputs to both HLS stream and storage to avoid camera access conflicts
- **Background Processing**: Runs camera streaming in a separate thread to avoid blocking main process
- **Configurable Settings**: Supports resolution, framerate, vertical flip, and segment duration
- **Dynamic Recording Control**: Can start/stop storage recording without interrupting HLS stream

### Published Settings

- `is_recording`: Boolean setting to start/stop storage recording (settable via UI/MQTT)
  - `False`: HLS streaming continues but no files are saved to disk
  - `True`: HLS streaming continues AND video segments are saved to storage

### Configuration Options

Located in `additional_config.ini`:
- `save_dir`: Directory for storing raw video files (default: `/home/pioreactor/data/camera`)
- `hls_dir`: Directory for HLS streaming files (default: `/var/www/pioreactorui/data`)
- `segment_duration_minutes`: Length of each video segment in minutes (default: 15)
- `width`: Video width in pixels (default: 1920)
- `height`: Video height in pixels (default: 1080)
- `framerate`: Video framerate (default: 30)
- `vflip`: Vertical flip for camera orientation (default: true)

### Streaming and Recording Process

1. **Job Start**: Initializes directories and configuration, starts camera streaming immediately
2. **Continuous HLS Streaming**: Single `rpicam-vid` process streams H.264 video to FFmpeg for HLS generation
3. **Stream Splitting**: Camera output is processed in chunks and sent to both HLS stream and conditionally to file storage
4. **Dynamic Recording**: When `is_recording` is enabled, the same video chunks are saved to segmented H.264 files
5. **Segment Management**: Creates new storage files based on configured segment duration (default 15 minutes)
6. **Cleanup**: Manages old HLS segments to prevent disk space issues
7. **Error Handling**: Logs errors and automatically restarts camera streaming if needed

### Hardware Requirements

- Raspberry Pi with camera module (libcamera-compatible)
- FFmpeg installed for HLS streaming
- Sufficient storage space for video files (only when recording is enabled)
- Network bandwidth consideration for HLS streaming

### UI Integration

The plugin integrates with the Pioreactor web UI through:
- `webcam_recorder.yaml`: Defines the job interface with recording toggle controls
- Real-time HLS streaming accessible immediately when job starts
- Dynamic storage recording control via `is_recording` setting
- Configurable camera and recording settings

### Dependencies

- `pioreactor>=23.6.0`: Core Pioreactor framework
- `rpicam-vid`: Raspberry Pi camera video capture (system dependency)
- `ffmpeg`: Video processing for HLS streaming (system dependency)

## Development Workflow

1. **Local Development**: Install with `pip install -e .` for development
2. **Camera Testing**: Verify camera functionality with `rpicam-vid --help`
3. **Configuration**: Test different camera settings in `additional_config.ini`
4. **Streaming Testing**: Start job and verify HLS stream is immediately available
5. **Recording Testing**: Toggle `is_recording` setting and verify file storage behavior
6. **UI Testing**: Check job controls and streaming in web interface
7. **Log Monitoring**: Watch `/var/log/pioreactor.log` for streaming and recording status

## Plugin Metadata

- **Name**: webcam_recorder
- **Version**: 1.0.0
- **Author**: Noah (noah@changebio.uk)
- **Description**: Webcam recorder plugin for continuous HLS streaming with optional video recording
- **Homepage**: https://github.com/pioreactor/pioreactor-webcam

## Best Practices

- **Storage Management**: Monitor disk usage for video files (only applies when recording is enabled)
- **Camera Resources**: Single camera process handles both streaming and recording - no conflicts
- **Network Bandwidth**: Consider HLS segment size for streaming over network
- **Streaming vs Recording**: HLS streaming starts immediately; storage recording is optional and controllable
- **Error Recovery**: Plugin automatically restarts camera streaming after failures
- **Thread Safety**: Camera streaming runs in background thread to avoid blocking main process
- **Dynamic Control**: Can toggle storage recording on/off without affecting live stream