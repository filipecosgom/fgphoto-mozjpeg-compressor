# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Security verification module for MozJPEG release URLs and SHA-256 digests
- Download-size and ZIP archive safety limits
- Automated tests for release validation, digest checks, and archive traversal

### Changed

- MozJPEG installation now discovers compatible official releases dynamically
- Thumbnail `PhotoImage` creation is kept on Tk's main thread
- Custom output suffixes are validated and constrained to the export directory
- Application interface and developer documentation are written in English

## [1.0.0] - 2026-04-28

### Added

- Initial release of MozJPEG Compressor
- Modern dark-themed GUI using customtkinter
- Batch compression support for JPEG and PNG images
- Dual view mode: List and Grid view with thumbnails
- Image preview panel with zoom, pan, and comparison (original vs compressed)
- Multi-select file handling: individual, range, and bulk selection
- Automatic image resizing before compression (with multiple preset options)
- Advanced compression settings (quality, progressive JPEG, chroma subsampling, DCT method, Huffman optimization, grayscale, quantization tables, smoothing)
- Folder browsing and recursive directory scanning
- Configurable output naming (automatic suffix, custom, or original name)
- Output file size tracking and compression ratio statistics
- Automatic MozJPEG (v4.1.5) download and installation for first-time users
- Real-time progress tracking during batch operations
- Export folder auto-open after compression completes
- Comprehensive tooltips for all compression options
- Windows 7+ compatibility (64-bit)
- MIT License

### Components

- **Tooltip System** - Hover help for all compression controls
- **DownloadWindow** - Auto-install MozJPEG with progress tracking
- **Compressor Thread** - Background processing worker with resize support
- **PreviewPanel** - Dual-image viewer with zoom and pan controls
- **SettingsPanel** - Basic and advanced compression options
- **App** - Main application with split layout (settings + file list + preview)

---

## Planned Features (Future Releases)

- [ ] Support for WebP and HEIC formats
- [ ] Batch scheduling and delayed processing
- [ ] Drag-and-drop file import
- [ ] Compression presets (web, mobile, print)
- [ ] EXIF data preservation option
- [ ] Dark/Light theme toggle
- [ ] Multi-language UI support
- [ ] CLI version for automation
- [ ] Integration with cloud storage services
