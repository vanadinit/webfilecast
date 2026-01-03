# Changelog

All notable changes to this project will be in this document.

## [1.1.1] - 2026-01-03

### Added
- Added a GitHub workflow (`python-publish.yml`) to automatically build and publish the package to PyPI on new releases.

### Fixed
- Prevented a `KeyError` when processing video files that have no `tags` in their metadata.

## [1.1.0] - 2026-01-03

### Added
- Switched build system to `pyproject.toml`.
- Complete UI redesign with a modern, dark theme.
- File list is now a searchable dropdown component.
- Search supports exact phrases in quotes (e.g., `"Series 7"`) and combined terms.
- Natural sorting for file list (e.g., "Episode 2" comes before "Episode 10").
- Connection status is now an elegant dot in the main title.
- Buttons now use icons (▶️, ⏹️, 📺, 🌐) with tooltips for a cleaner look.
- "Open in Browser" button (🌐) appears when server is started.
- Placeholder texts for file info and language selection for a cleaner initial view.

### Changed
- Updated `terminalcast` dependency and adapted code for compatibility.
- The file list now loads automatically on connection.
- The "Refresh List" button is now an icon (🔄) next to the file list.
- During a file scan, the refresh button is disabled and shows the number of scanned files.
- Playback buttons (Chromecast, Browser) are now disabled until the server is started.
- The server no longer starts implicitly when "Play on Chromecast" is clicked.
- Language selection dropdown now automatically selects the language if only one is available.
- Improved layout for action buttons and status display on desktop and mobile.

### Fixed
- Corrected handling of `audio_index` for `create_tmp_video_file`.
- Corrected IP/Host handling for `TerminalCast` initialization.
- Fixed layout overlap between search bar and refresh button.
- Fixed a bug where the single-language detection in the UI could fail.

## [1.0.0] - 2023-12-28

- Initial release of webfilecast.
- Basic functionality to select and play local video files on a Chromecast.
