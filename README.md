# MozJPEG Compressor

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%207%2B-0078D4?style=flat-square&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Release](https://img.shields.io/badge/Release-v1.0.0-brightgreen?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-success?style=flat-square)

A modern, lightweight GUI application for batch-compressing JPEG and PNG images using MozJPEG on Windows. Features dual view modes (list & grid), real-time preview, advanced compression options, and automatic MozJPEG installation.

## ✨ Features

- **Modern Dark Theme** — Clean, intuitive interface built with customtkinter
- **Batch Processing** — Compress multiple files in one operation
- **Dual View Modes** — Switch between list and grid view with thumbnails
- **Live Preview** — Compare original vs. compressed with zoom and pan
- **Multi-Select** — Select files individually, by range, or all at once
- **Smart Scaling** — Optional image resizing before compression
- **Advanced Settings**:
  - Quality adjustment (0-100)
  - Progressive JPEG support
  - Chroma subsampling (4:2:0, 4:2:2, 4:4:4)
  - DCT method selection (int, float, fast)
  - Huffman optimization
  - Grayscale conversion
  - Quantization tables
  - Smoothing filters
- **Automatic Setup** — Auto-download and install MozJPEG v4.1.5
- **Statistics** — Track space saved and compression ratios
- **Organized Output** — Maintains folder structure in export directory
- **Recursive Scan** — Process subdirectories with hierarchy preservation
- **Intelligent Skipping** — Avoids re-compressing existing files

## 📋 Requirements

- **Windows 7 or higher** (64-bit)
- **Python 3.8 or higher**
- Internet connection (first-time setup only for MozJPEG download)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/filipecosgom/fgphoto-mozjpeg-compressor.git
cd fgphoto-mozjpeg-compressor
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python main.py
```

## 📖 Usage Guide

### First Launch

1. Run `python main.py`
2. The app automatically checks for MozJPEG installation
3. If missing, a download dialog appears — click OK and wait for setup
4. Application is ready to use

### Basic Workflow

1. **Select Source Folder** — Click the 📁 icon to browse
2. **Configure Settings** — Adjust quality (75-85 recommended for web)
3. **Find Files** — Click "🔍 Find Files" to scan directory
4. **Select Images** — Choose individual files or use selection buttons
5. **Start Compression** — Click "▶ Start Compression"
6. **Review Results** — Compressed files appear in `export/` folder

### Example Folder Structure

**Before:**
```
Photos/
├─ 2024/
│  ├─ beach.jpg    (8.2 MB)
│  └─ mountain.jpg (6.5 MB)
└─ 2023/
   └─ car.png      (4.1 MB)
```

**After compression (Quality 80):**
```
Photos/export/
├─ 2024/
│  ├─ beach_compressed_80.jpg    (1.8 MB) ← 78% reduction
│  └─ mountain_compressed_80.jpg (1.4 MB) ← 78% reduction
└─ 2023/
   └─ car_compressed_80.jpg      (0.9 MB) ← 78% reduction
```

## ⚙️ Compression Settings

### Quality (0-100)
- **75-85** — Sweet spot for web delivery (recommended)
- **90+** — High fidelity, larger files
- **<60** — Visible artifacts
- MozJPEG typically saves 10-20% vs standard JPEG

### Progressive JPEG
Images load gradually in browsers (low-quality preview first). Recommended for web.

### Chroma Subsampling
- **4:2:0 (2x2)** — Smaller files, minimal quality loss (default, recommended)
- **4:2:2 (2x1)** — Balanced approach
- **4:4:4 (1x1)** — Maximum fidelity, larger files

### Image Resizing
Reduce dimensions before compression, preserving aspect ratio:
- 75%, 50%, 25% of original size
- Custom pixel value for longest edge
Example: 2000px max → 6000×4000 → 2000×1333

### Other Options
| Option | Effect |
|--------|--------|
| **Huffman Optimization** | 3-5% size reduction, no quality loss |
| **Grayscale Conversion** | Remove all color information |
| **DCT Method** | `int` (recommended), `float`, or `fast` |
| **Quantization Table** | 0 (standard), 1 (MozJPEG optimized, recommended) |
| **Smoothing** | Reduce sensor noise before compression |

### Advanced Options
- **Minimum File Size** — Skip files below threshold (default: 100 KB)
- **Output Naming** — Auto suffix, custom prefix, or original name
- **Recursive Processing** — Include subdirectories
- **Auto-Open Export** — Open folder when done

## 🐛 Troubleshooting

### MozJPEG Installation Fails
1. Download manually: https://github.com/mozilla/mozjpeg/releases
2. Install to `C:\Program Files\Mozilla\MozJPEG\`
3. Restart the application

### Compression Fails for Specific Files
- Verify file is valid JPEG or PNG
- Check if file is corrupted
- Try with quality ≥ 50
- Check available disk space

### Slow Thumbnail Loading
- Reduce number of files
- Use image resizing before compression
- Increase minimum file size threshold
- Enable batch mode for faster processing

### Application Freezes
- Compression is multi-threaded but large batches take time
- Reduce quality if processing hangs
- Watch the progress bar at the top

## 📁 User Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│ Header: Folder Selection & Recursive Options            │
├──────────────────┬──────────────────────────────────────┤
│                  │                                      │
│  Left Panel:     │      Right Panel:                   │
│  • Output Mode   │  • File List / Grid View            │
│  • Min Size      │  • Selection Controls               │
│  • Resize Opts   │  • Progress Bar                     │
│  • Quality       │                                     │
│  • Compression   │  • Image Preview                    │
│    Settings      │  • Zoom Controls                    │
│  • Buttons       │  • File Statistics                  │
│                  │  • Compression Results              │
└──────────────────┴──────────────────────────────────────┘
```

## 🔐 Security & Privacy

- No files uploaded online
- All processing is local
- EXIF data removed during compression
- No telemetry or tracking
- Open source — audit the code anytime

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Reporting bugs
- Requesting features
- Submitting pull requests
- Code style and standards

## 📚 Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

## 🔗 Resources

- [MozJPEG](https://github.com/mozilla/mozjpeg) — JPEG encoder
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern UI toolkit
- [Pillow](https://python-pillow.org/) — Image processing
- [Semantic Versioning](https://semver.org) — Version scheme

---

**Built with ❤️ for efficient image compression**  
Author: [@filipecosgom](https://github.com/filipecosgom)  
Created: April 2026
Se mudares para 70%, os novos ficheiros têm sufixo `_compressed_70.jpg` e são processados normalmente.

## Localização do MozJPEG

O binário é guardado em:  
`%APPDATA%\MozJPEGCompressor\bin\cjpeg.exe`
