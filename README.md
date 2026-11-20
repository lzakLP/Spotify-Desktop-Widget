# Spotify Desktop Widget V.1

A lightweight floating desktop music widget for Windows 10 and Windows 11. Built with Python and PySide6, it uses the Windows Global System Media Transport Controls (GSMTC) API to display Spotify playback information and provide basic playback controls.

## Features

- Displays the current track title and artist.
- Displays the track's album artwork.
- Play/pause, previous-track, and next-track controls.
- Clickable playback progress bar for seeking.
- Floating, frameless desktop interface that stays on top.
- Drag the widget to reposition it.
- Automatically adapts its accent and background colors to the album artwork.
- Context menu to toggle the always-on-top behavior or exit.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer (64-bit recommended).
- Spotify desktop application installed and running when you want to control Spotify.
- pip, included with standard Python installations.
- Internet access for installing the Python dependencies.

The application relies on Windows media session APIs. It is not designed for macOS or Linux.

## Installation

1. Clone this repository:

   ```powershell
   git clone https://github.com/lzakLP/Spotify-Desktop-Widget.git
   cd Spotify-Desktop-Widget
   ```

2. (Recommended) Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks script activation, use Command Prompt instead:

   ```bat
   .venv\Scripts\activate.bat
   ```

3. Install the dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Run

Start the Spotify desktop application, then run:

```powershell
python spotify_widget.py
```

The widget opens near the bottom-right corner of the primary display.

## Controls

| Action | Behavior |
| --- | --- |
| Drag with the left mouse button | Move the widget |
| Click the progress bar | Seek to the selected position in the track |
| Previous button | Play the previous track |
| Play/Pause button | Toggle playback |
| Next button | Skip to the next track |
| Right-click the widget | Open the context menu |
| Always on top | Toggle the window's always-on-top state |
| Exit | Close the widget |

## Build an executable with PyInstaller

PyInstaller can package the application as a Windows executable.

1. Install PyInstaller in the same virtual environment:

   ```powershell
   pip install pyinstaller
   ```

2. Build the executable:

   ```powershell
   pyinstaller --noconfirm --clean --windowed --name SpotifyDesktopWidget --collect-submodules winrt.windows.media.control --collect-submodules winrt.windows.storage.streams spotify_widget.py
   ```

3. The executable is typically generated under:

   ```
   dist/SpotifyDesktopWidget/SpotifyDesktopWidget.exe
   ```

PyInstaller packaging may require additional hidden-import or collection options depending on the installed PyWinRT and PySide6 versions. Test the packaged application on a clean Windows environment. Running from source is the baseline execution method.

## How it works

- **Interface:** PySide6 provides the frameless floating window, playback controls, progress display, and album artwork rendering.
- **Media integration:** PyWinRT accesses Windows Global System Media Transport Controls sessions.
- **Asynchronous polling:** A dedicated asyncio event loop runs in a background thread and periodically reads the active media session.
- **Artwork colors:** The dominant color sampled from the artwork is used to update the widget's visual theme.

The widget first looks for a media session whose application identifier contains `spotify`. If one is not found, the current Windows media session may be used as a fallback.

## Troubleshooting

- **No track information appears:** Make sure Spotify is open and exposing a Windows media session.
- **Another media player is displayed:** The current implementation can fall back to the current Windows media session when it does not find a Spotify session.
- **Dependency installation fails:** Confirm that you are using a supported 64-bit Python installation on Windows, upgrade pip, and retry.
- **The executable does not start:** Run the Python source version first to distinguish packaging issues from runtime or dependency issues.

## Limitations

- Windows-only: the application depends on Windows media session APIs.
- Spotify must expose a compatible Windows media session for Spotify-specific playback information and controls.
- The current implementation is a lightweight widget, not a full Spotify client.
- PyInstaller builds have not been validated across different Windows machines and Python environments.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Disclaimer

This is an independent project and is not affiliated with, endorsed by, or sponsored by Spotify. Spotify is a trademark of Spotify AB.
