#!/usr/bin/env python3
"""
MozJPEG GUI Compressor - Windows
Compress JPEG/PNG images with MozJPEG through a graphical interface.

Dependencies: customtkinter, Pillow, requests
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import shutil
import subprocess
import threading
import requests
import tempfile
from pathlib import Path
from PIL import Image, ImageTk

# ─── Global configuration ─────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# GitHub API endpoint used to discover the newest MozJPEG release that
# actually provides a Windows x64 binary.  We deliberately do not use
# /releases/latest directly because the newest release may not contain a
# Windows binary (this has happened with MozJPEG releases).
MOZJPEG_RELEASES_API = "https://api.github.com/repos/mozilla/mozjpeg/releases"
MOZJPEG_RELEASES_PAGE_SIZE = 30


def _asset_score(asset_name: str) -> int:
    """Rank downloadable Windows x64 assets, rejecting unrelated archives."""
    name = asset_name.lower()
    if not name.endswith((".exe", ".zip")):
        return -1

    if any(x in name for x in ("source", "src", "linux", "macos", "darwin", "osx")):
        return -1
    if not any(x in name for x in ("win", "windows")):
        return -1
    if not any(x in name for x in ("x64", "win64", "amd64", "64-bit", "64bit")):
        return -1

    score = 0
    if name.endswith(".exe"):
        score += 100
    if "win64" in name or "windows-x64" in name or "windows_x64" in name:
        score += 20
    if "amd64" in name or "x64" in name:
        score += 10
    if "setup" in name or "installer" in name:
        score += 5
    return score


def _find_cjpeg_in_directory(directory: Path) -> Path | None:
    """Find cjpeg.exe recursively below a directory."""
    direct = directory / "cjpeg.exe"
    if direct.is_file():
        return direct
    try:
        for candidate in directory.rglob("cjpeg.exe"):
            if candidate.is_file():
                return candidate
    except OSError:
        pass
    return None


def get_latest_windows_mozjpeg_asset():
    """Query GitHub and return ``(tag, filename, download_url)`` for a release."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MozJPEGCompressor/1.0",
    }

    releases = []
    for page in range(1, 4):
        response = requests.get(
            MOZJPEG_RELEASES_API,
            params={"per_page": MOZJPEG_RELEASES_PAGE_SIZE, "page": page},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        releases.extend(batch)
        if len(batch) < MOZJPEG_RELEASES_PAGE_SIZE:
            break

    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue

        candidates = []
        for asset in release.get("assets", []):
            score = _asset_score(asset.get("name", ""))
            if score >= 0 and asset.get("browser_download_url"):
                candidates.append((score, asset))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            asset = candidates[0][1]
            return (
                release.get("tag_name", "unknown"),
                asset["name"],
                asset["browser_download_url"],
            )

    raise RuntimeError(
        "No Windows x64 MozJPEG binary was found in the available "
        "public GitHub releases."
    )


def _safe_extract_zip(zip_path: Path, destination: Path) -> None:
    """Extract a ZIP after rejecting members that escape ``destination``."""
    import zipfile

    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise RuntimeError("The ZIP file contains an invalid path.")
        zf.extractall(destination)


def _verify_cjpeg(cjpeg: Path) -> Path:
    """Verify that ``cjpeg.exe`` exists and returns success for ``-version``."""
    if not cjpeg or not cjpeg.is_file():
        raise RuntimeError("cjpeg.exe was not found after installation.")

    try:
        result = subprocess.run(
            [str(cjpeg), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            f"cjpeg.exe was found but could not be executed: {exc}"
        ) from exc

    if result.returncode != 0:
        output = (result.stdout or result.stderr or "").strip()
        raise RuntimeError(
            "cjpeg.exe was found but did not respond correctly"
            + (f": {output}" if output else ".")
        )

    return cjpeg
APP_DIR = Path(os.getenv("APPDATA", ".")) / "MozJPEGCompressor"
BIN_DIR = APP_DIR / "bin"
CJPEG_EXE = BIN_DIR / "cjpeg.exe"
EXPORT_FOLDER = "export"
SUPPORTED = {".jpg", ".jpeg", ".png"}

# Color palette
C_BG = "#0d0d14"
C_SURFACE = "#13131e"
C_CARD = "#191926"
C_HOVER = "#21212f"
C_BORDER = "#2a2a3d"
C_ACCENT = "#f97316"
C_ACCENT2 = "#fb923c"
C_TEXT = "#e4e4f0"
C_MUTED = "#5e5e8a"
C_SUBTLE = "#3a3a58"
C_OK = "#22c55e"
C_ERR = "#ef4444"
C_WARN = "#f59e0b"
C_SELECTED = "#2d4a2c"  # dark green background for selected files

# ─── Help text ────────────────────────────────────────────────────────────────

TIPS = {
    "quality": (
        "Final image quality (0-100).\n\n"
        "75-85 -> good balance for the web\n"
        "90+   -> high fidelity, larger files\n"
        "< 60  -> visible artifacts\n\n"
        "MozJPEG produces files ~10-20% smaller\n"
        "than standard JPEG at the same quality."
    ),
    "progressive": (
        "Progressive JPEG: the image loads gradually\n"
        "in browsers, showing a blurred preview\n"
        "before loading is complete.\n\n"
        "Recommended for web images."
    ),
    "chroma": (
        "Chroma subsampling - how color information\n"
        "is stored.\n\n"
        "4:2:0 (2x2) -> smaller files, minor color loss\n"
        "4:2:2 (2x1) -> good compromise\n"
        "4:4:4 (1x1) -> maximum fidelity, larger files\n\n"
        "For general photography, 4:2:0 is sufficient."
    ),
    "dct": (
        "DCT calculation method\n"
        "(Discrete Cosine Transform).\n\n"
        "int   -> fast, sufficient quality (recommended)\n"
        "float -> slower, slightly better\n"
        "fast  -> fastest, lower quality"
    ),
    "optimize": (
        "Optimizes Huffman tables for each\n"
        "individual image.\n\n"
        "Reduces file size by 3-5% with no quality loss.\n"
        "Makes processing slightly slower."
    ),
    "grayscale": (
        "Converts the image to grayscale.\n"
        "Removes all color information.\n\n"
        "Useful for documents, monochrome images,\n"
        "or when color is not relevant."
    ),
    "quant_table": (
        "Quantization table - defines how frequency\n"
        "details are discarded during compression.\n\n"
        "0 -> standard JPEG table\n"
        "1 -> optimized MozJPEG table (recommended)\n"
        "2 -> alternative MozJPEG table\n"
        "3+ -> experimental tables"
    ),
    "smooth": (
        "Smoothing applied to the image before compression\n"
        "(0–100).\n\n"
        "0     -> no smoothing\n"
        "10-20 -> reduces sensor noise\n"
        "100   -> maximum smoothing (may blur the image)\n\n"
        "Useful for noisy images."
    ),
    "recursive": (
        "Also process images in subfolders.\n\n"
        "The subfolder structure is replicated inside\n"
        "the 'export' folder.\n\n"
        "Example:\n"
        "Fotos/2024/jan/img.jpg\n"
        "→ Fotos/export/2024/jan/img_compressed_80.jpg"
    ),
    "min_size": (
        "Skip files below this size.\n\n"
        "Small images were probably already compressed\n"
        "at the source - MozJPEG rarely reduces them\n"
        "without visible loss.\n\n"
        "100 KB is a good default value."
    ),
    "resize": (
        "Resize the image before compression,\n"
        "preserving the original width:height ratio.\n\n"
        "The value defines the longest side (width or height,\n"
        "depending on the image orientation).\n\n"
        "Example: 2000px on a 6000x4000 photo\n"
        "-> result: 2000x1333\n\n"
        "Done before compression to avoid\n"
        "double quality degradation."
    ),
}


# ─── Utilities ────────────────────────────────────────────────────────────────


def fmt_size(n: int) -> str:
    """Format a byte count for display in the results table and preview."""
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


def find_cjpeg() -> Path | None:
    """Find MozJPEG in the managed folder, common install folders, or PATH."""
    if CJPEG_EXE.exists():
        return CJPEG_EXE
    # Check common MozJPEG installation locations.
    fallbacks = [
        Path("C:/Program Files/Mozilla/MozJPEG/cjpeg.exe"),
        Path("C:/Program Files (x86)/Mozilla/MozJPEG/cjpeg.exe"),
    ]
    for p in fallbacks:
        if p.exists():
            # Copy the executable into the managed application directory.
            BIN_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, CJPEG_EXE)
            return CJPEG_EXE
    which = shutil.which("cjpeg")
    return Path(which) if which else None


# ─── Tooltip ─────────────────────────────────────────────────────────────────


class Tooltip:
    _current: "Tooltip | None" = None

    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.win: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<Button>", self._hide)

    def _show(self, _=None):
        if Tooltip._current and Tooltip._current is not self:
            Tooltip._current._hide()
        if self.win:
            return
        Tooltip._current = self
        rx = self.widget.winfo_rootx() + 30
        ry = self.widget.winfo_rooty()
        self.win = w = tk.Toplevel(self.widget)
        w.wm_overrideredirect(True)
        w.attributes("-topmost", True)
        outer = tk.Frame(
            w,
            bg="#1e1e2e",
            bd=1,
            relief="solid",
            highlightbackground=C_BORDER,
            highlightthickness=1,
        )
        outer.pack()
        tk.Label(
            outer,
            text=self.text,
            justify="left",
            bg="#1e1e2e",
            fg="#c8c8e8",
            font=("Segoe UI", 12),
            padx=12,
            pady=8,
            wraplength=290,
        ).pack()
        w.update_idletasks()
        sw = w.winfo_screenwidth()
        if rx + w.winfo_width() > sw:
            rx = self.widget.winfo_rootx() - w.winfo_width() - 4
        w.wm_geometry(f"+{rx}+{ry}")

    def _hide(self, _=None):
        if self.win:
            self.win.destroy()
            self.win = None
        if Tooltip._current is self:
            Tooltip._current = None


def qmark(parent: tk.Widget, key: str, **kw) -> ctk.CTkButton:
    """Create a help button with the tooltip associated with ``key``."""
    b = ctk.CTkButton(
        parent,
        text="?",
        width=20,
        height=20,
        corner_radius=10,
        font=("Segoe UI", 9, "bold"),
        fg_color=C_HOVER,
        hover_color=C_BORDER,
        text_color=C_MUTED,
        **kw,
    )
    Tooltip(b, TIPS[key])
    return b


# ─── Download window ──────────────────────────────────────────────────────────


class DownloadWindow(ctk.CTkToplevel):
    """Download and install MozJPEG without blocking the main Tk event loop."""

    def __init__(self, parent: ctk.CTk, on_done):
        super().__init__(parent)
        self._on_done = on_done
        self.title("Install MozJPEG")
        self.geometry("500x240")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.after(400, lambda: threading.Thread(target=self._run, daemon=True).start())

    def _build(self):
        ctk.CTkLabel(
            self,
            text="MozJPEG not found",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self,
            text="Searching for and installing the latest available version...",
            font=("Segoe UI", 10),
            text_color=C_MUTED,
        ).pack(pady=(0, 16))
        self._lbl = ctk.CTkLabel(self, text="Preparing...", font=("Segoe UI", 10))
        self._lbl.pack(pady=(0, 8))
        self._bar = ctk.CTkProgressBar(self, width=420, progress_color=C_ACCENT)
        self._bar.set(0)
        self._bar.pack(pady=(0, 4))

    def _set(self, text: str, val: float | None = None):
        self._lbl.configure(text=text)
        if val is not None:
            self._bar.set(max(0.0, min(1.0, val)))

    def _download(self, url: str, destination: Path):
        """Stream a release asset to disk and report progress on the UI thread."""
        headers = {"User-Agent": "MozJPEGCompressor/1.0"}
        with requests.get(url, stream=True, timeout=90, headers=headers) as r:
            r.raise_for_status()
            total_header = r.headers.get("content-length")
            try:
                total = int(total_header) if total_header else 0
            except ValueError:
                total = 0

            done = 0
            with destination.open("wb") as f:
                for chunk in r.iter_content(65536):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.after(0, self._bar.set, min(0.80, done / total * 0.80))

        if destination.stat().st_size == 0:
            raise RuntimeError("The MozJPEG download produced an empty file.")

    def _install_asset(self, asset_path: Path, asset_name: str) -> Path:
        """Install an EXE or extract a ZIP, returning the managed cjpeg path."""
        name = asset_name.lower()

        if name.endswith(".zip"):
            self.after(0, self._set, "Extracting MozJPEG...", 0.82)
            extract_dir = BIN_DIR / "_download_extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                _safe_extract_zip(asset_path, extract_dir)
                found = _find_cjpeg_in_directory(extract_dir)
                if not found:
                    raise RuntimeError("The downloaded ZIP does not contain cjpeg.exe.")

                BIN_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(found, CJPEG_EXE)
                for companion in found.parent.iterdir():
                    if companion.is_file() and companion.suffix.lower() in {".dll", ".exe"}:
                        if companion.name.lower() != "cjpeg.exe":
                            shutil.copy2(companion, BIN_DIR / companion.name)
            finally:
                shutil.rmtree(extract_dir, ignore_errors=True)

            return CJPEG_EXE

        if name.endswith(".exe"):
            self.after(0, self._set, "Installing MozJPEG...", 0.82)
            BIN_DIR.mkdir(parents=True, exist_ok=True)
            bin_dir_str = str(BIN_DIR).rstrip("\\")
            result = subprocess.run(
                [str(asset_path), "/S", f"/D={bin_dir_str}"],
                timeout=180,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"The MozJPEG installer exited with code {result.returncode}."
                )
            return CJPEG_EXE

        raise RuntimeError(f"Unsupported MozJPEG format: {asset_name}")

    def _run(self):
        """Coordinate discovery, download, installation, and verification."""
        tmp = None
        try:
            BIN_DIR.mkdir(parents=True, exist_ok=True)

            existing = find_cjpeg()
            if existing:
                self.after(0, self._set, "MozJPEG is already installed.", 1.0)
                self.after(500, self._finish, True)
                return

            self.after(0, self._set, "Searching for the latest Windows version...", 0.05)
            tag, asset_name, url = get_latest_windows_mozjpeg_asset()
            self.after(
                0,
                self._set,
                f"Downloading {tag} ({asset_name})...",
                0.10,
            )

            suffix = ".zip" if asset_name.lower().endswith(".zip") else ".exe"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                tmp = Path(f.name)

            self._download(url, tmp)

            self.after(0, self._set, "Installing and verifying MozJPEG...", 0.85)
            self._install_asset(tmp, asset_name)

            self.after(0, self._set, "Verifying cjpeg.exe...", 0.94)
            cjpeg = find_cjpeg()
            if not cjpeg:
                raise RuntimeError(
                    "cjpeg.exe was not found after installation. "
                    "The MozJPEG release structure may have changed."
                )
            _verify_cjpeg(cjpeg)

            self.after(0, self._set, f"MozJPEG {tag} installed successfully!", 1.0)
            self.after(900, self._finish, True)

        except Exception as e:
            self.after(0, self._fail, str(e))
        finally:
            if tmp:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    def _finish(self, success: bool):
        on_done = self._on_done
        self.destroy()
        on_done(success)

    def _fail(self, msg: str):
        messagebox.showerror(
            "Installation failed",
            f"MozJPEG could not be installed automatically.\n\n"
            f"Error: {msg}\n\n"
            f"Install it manually from:\n"
            f"https://github.com/mozilla/mozjpeg/releases",
        )
        self._finish(False)


# ─── Compression worker ───────────────────────────────────────────────────────


class Compressor(threading.Thread):
    """Process selected images in a worker thread and report results via callbacks."""

    def __init__(
        self,
        cjpeg: Path,
        tasks: list,
        settings: dict,
        on_file_done,
        on_progress,
        on_finish,
    ):
        super().__init__(daemon=True)
        self.cjpeg = cjpeg
        self.tasks = tasks  # list of (input Path, output Path) pairs
        self.settings = settings
        self.on_file_done = on_file_done
        self.on_progress = on_progress
        self.on_finish = on_finish
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        total = len(self.tasks)
        for i, (inp, out) in enumerate(self.tasks):
            if self._stop_event.is_set():
                break
            self.on_progress(i, total, inp)
            result = self._process(inp, out)
            self.on_file_done(inp, result)
        self.on_finish()

    def _process(self, inp: Path, out: Path) -> dict:
        """Optionally resize an image, run cjpeg, and return a result record."""
        out.parent.mkdir(parents=True, exist_ok=True)
        s = self.settings
        q = s["quality"]

        # ── Resize com Pillow (antes do cjpeg) ───────────────────────────────
        resize_mode = s.get("resize_mode", "none")
        source = inp
        tmp_path: Path | None = None

        if resize_mode != "none":
            try:
                img = Image.open(inp)
                w, h = img.size
                if resize_mode == "custom":
                    max_side = s.get("resize_px", 2000)
                    if max(w, h) > max_side:
                        ratio = max_side / max(w, h)
                        img = img.resize(
                            (max(1, int(w * ratio)), max(1, int(h * ratio))),
                            Image.LANCZOS,
                        )
                else:
                    pct = int(resize_mode) / 100
                    img = img.resize(
                        (max(1, int(w * pct)), max(1, int(h * pct))),
                        Image.LANCZOS,
                    )
                tmp_path = Path(tempfile.mktemp(suffix=".png"))
                img.save(tmp_path, "PNG")
                source = tmp_path
            except Exception as e:
                return {"status": "error", "msg": f"Resize failed: {e}"}

        # ── Comando cjpeg ─────────────────────────────────────────────────────
        cmd = [str(self.cjpeg), "-quality", str(q)]

        if s.get("progressive"):
            cmd.append("-progressive")

        cmd += ["-dct", s.get("dct", "int")]
        cmd += ["-sample", s.get("chroma", "2x2")]

        if s.get("optimize"):
            cmd.append("-optimize")

        if s.get("grayscale"):
            cmd.append("-grayscale")

        qt = s.get("quant_table", 0)
        if qt:
            cmd += ["-quant-table", str(qt)]

        sm = s.get("smooth", 0)
        if sm:
            cmd += ["-smooth", str(sm)]

        cmd += ["-outfile", str(out), str(source)]

        try:
            orig_sz = inp.stat().st_size
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            if r.returncode != 0:
                return {
                    "status": "error",
                    "msg": r.stderr.decode(errors="replace").strip()
                    or "Unknown error",
                }
            comp_sz = out.stat().st_size
            return {
                "status": "done",
                "orig": orig_sz,
                "comp": comp_sz,
                "pct": (1 - comp_sz / orig_sz) * 100,
                "out": out,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "msg": "Timeout (file may be too large)."}
        except Exception as e:
            return {"status": "error", "msg": str(e)}
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


# ─── Preview panel ────────────────────────────────────────────────────────────


class PreviewPanel(ctk.CTkFrame):
    """Display original and compressed images with zooming and panning."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._zoom = 1.0
        self._px = self._py = 0.0
        self._drag: tuple | None = None
        self._orig_img: Image.Image | None = None
        self._comp_img: Image.Image | None = None
        self._build()

    def _build(self):
        # Top bar: labels and zoom controls.
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 3))

        ctk.CTkLabel(
            top,
            text="ORIGINAL",
            font=("Segoe UI", 12, "bold"),
            text_color=C_MUTED,
        ).pack(side="left", expand=True)

        zf = ctk.CTkFrame(top, fg_color="transparent")
        zf.pack(side="left")
        for txt, cmd in [
            ("−", lambda: self._step(-0.25)),
            ("+", lambda: self._step(+0.25)),
            ("↺", self._reset),
        ]:
            ctk.CTkButton(
                zf,
                text=txt,
                width=26,
                height=22,
                fg_color=C_HOVER,
                hover_color=C_BORDER,
                text_color=C_TEXT,
                font=("Segoe UI", 11),
                command=cmd,
            ).pack(side="left", padx=1)
        self._zlbl = ctk.CTkLabel(
            zf, text="100%", font=("Segoe UI", 9), text_color=C_MUTED, width=44
        )
        self._zlbl.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(
            top,
            text="COMPRESSED",
            font=("Segoe UI", 9, "bold"),
            text_color=C_MUTED,
        ).pack(side="right", expand=True)

        # Canvases
        cf = tk.Frame(self, bg=C_BG)
        cf.pack(fill="both", expand=True, padx=10)
        self._co = tk.Canvas(cf, bg=C_BG, bd=0, highlightthickness=0, cursor="fleur")
        self._co.pack(side="left", fill="both", expand=True)
        tk.Frame(cf, bg=C_BORDER, width=2).pack(side="left", fill="y")
        self._cc = tk.Canvas(cf, bg=C_BG, bd=0, highlightthickness=0, cursor="fleur")
        self._cc.pack(side="right", fill="both", expand=True)

        # Bottom bar: file-size information.
        inf = ctk.CTkFrame(self, fg_color="transparent")
        inf.pack(fill="x", padx=10, pady=(3, 10))
        self._lbl_orig = ctk.CTkLabel(
            inf, text="—", font=("Segoe UI", 9), text_color=C_MUTED
        )
        self._lbl_orig.pack(side="left", expand=True)
        self._lbl_comp = ctk.CTkLabel(
            inf, text="—", font=("Segoe UI", 9), text_color=C_MUTED
        )
        self._lbl_comp.pack(side="right", expand=True)

        # Mouse and resize events.
        for c in (self._co, self._cc):
            c.bind("<MouseWheel>", self._wheel)
            c.bind("<ButtonPress-1>", self._drag_start)
            c.bind("<B1-Motion>", self._pan)
            c.bind("<Configure>", lambda _: self._draw())

    def load(self, orig_path: Path, comp_path: Path | None = None):
        """Load preview images and reset the view to 100 percent."""
        self._px = self._py = 0.0
        self._zoom = 1.0
        try:
            self._orig_img = Image.open(orig_path)
        except Exception:
            self._orig_img = None
        try:
            self._comp_img = (
                Image.open(comp_path) if comp_path and comp_path.exists() else None
            )
        except Exception:
            self._comp_img = None

        # Update displayed file sizes.
        if orig_path and orig_path.exists():
            self._lbl_orig.configure(
                text=fmt_size(orig_path.stat().st_size), text_color=C_MUTED
            )
        else:
            self._lbl_orig.configure(text="—", text_color=C_MUTED)

        if comp_path and comp_path.exists() and orig_path and orig_path.exists():
            os_sz = orig_path.stat().st_size
            cs_sz = comp_path.stat().st_size
            pct = (1 - cs_sz / os_sz) * 100 if os_sz else 0
            color = C_OK if pct > 0 else C_WARN
            self._lbl_comp.configure(
                text=f"{fmt_size(cs_sz)}   (−{pct:.1f}%)", text_color=color
            )
        else:
            self._lbl_comp.configure(text="Not compressed yet", text_color=C_MUTED)

        self._draw()

    def _draw_canvas(
        self, c: tk.Canvas, img: Image.Image | None, placeholder: str = "—"
    ):
        """Fit a preview image to its canvas while retaining the PhotoImage."""
        c.delete("all")
        w = c.winfo_width() or 1
        h = c.winfo_height() or 1
        if img is None:
            c.create_text(
                w // 2,
                h // 2,
                text=placeholder,
                fill=C_MUTED,
                font=("Segoe UI", 10),
            )
            return
        scale = min(w / img.width, h / img.height) * self._zoom
        nw = max(1, int(img.width * scale))
        nh = max(1, int(img.height * scale))
        try:
            resized = img.resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            c._ph = photo  # evita garbage collection
            c.create_image(
                w // 2 + int(self._px),
                h // 2 + int(self._py),
                image=photo,
                anchor="center",
            )
        except Exception:
            pass

    def _draw(self, *args, **kwargs):
        super()._draw(*args, **kwargs)

        # The canvas widgets are not available during early construction.
        if not hasattr(self, "_co"):
            return

        self._draw_canvas(self._co, self._orig_img, "No image")
        self._draw_canvas(self._cc, self._comp_img, "Not compressed yet")
        self._zlbl.configure(text=f"{int(self._zoom * 100)}%")

    def _wheel(self, e):
        factor = 1.15 if e.delta > 0 else (1 / 1.15)
        self._zoom = max(0.05, min(10.0, self._zoom * factor))
        self._draw()

    def _step(self, d: float):
        self._zoom = max(0.05, min(10.0, self._zoom + d))
        self._draw()

    def _reset(self):
        self._zoom, self._px, self._py = 1.0, 0.0, 0.0
        self._draw()

    def _drag_start(self, e):
        self._drag = (e.x, e.y)

    def _pan(self, e):
        if self._drag:
            self._px += e.x - self._drag[0]
            self._py += e.y - self._drag[1]
            self._drag = (e.x, e.y)
            self._draw()


# ─── Settings panel ───────────────────────────────────────────────────────────


class SettingsPanel(ctk.CTkFrame):
    """Own the compression controls and expose them as a plain settings dict."""

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=C_CARD, corner_radius=10, **kw)
        self._adv_open = False
        self._build()

    def _build(self):
        pad = {"padx": 14}

        ctk.CTkLabel(
            self,
            text="Compression",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(12, 0), **pad)

        # Quality slider.
        qrow = ctk.CTkFrame(self, fg_color="transparent")
        qrow.pack(fill="x", pady=(8, 0), **pad)
        ctk.CTkLabel(qrow, text="Quality", font=("Segoe UI", 10)).pack(side="left")
        qmark(qrow, "quality").pack(side="left", padx=(4, 0))
        self._qlbl = ctk.CTkLabel(
            qrow,
            text="80",
            font=("Segoe UI", 11, "bold"),
            text_color=C_ACCENT,
            width=32,
        )
        self._qlbl.pack(side="right")

        self._qslider = ctk.CTkSlider(
            self,
            from_=0,
            to=100,
            button_color=C_ACCENT,
            progress_color=C_ACCENT,
            command=lambda v: self._qlbl.configure(text=str(int(v))),
        )
        self._qslider.set(80)
        self._qslider.pack(fill="x", pady=(4, 10), **pad)

        # Divider.
        ctk.CTkFrame(self, height=1, fg_color=C_BORDER).pack(fill="x", padx=10)

        # Expand advanced settings button.
        self._adv_btn = ctk.CTkButton(
            self,
            text="▶   Advanced settings",
            font=("Segoe UI", 10),
            anchor="w",
            fg_color="transparent",
            hover_color=C_HOVER,
            text_color=C_MUTED,
            command=self._toggle_adv,
        )
        self._adv_btn.pack(fill="x", padx=6, pady=4)

        # Advanced settings frame, hidden by default.
        self._adv_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._build_adv(self._adv_frame)

    def _row(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=3)
        return f

    def _cb(self, parent, text: str, var: tk.BooleanVar, tip_key: str):
        row = self._row(parent)
        ctk.CTkCheckBox(
            row,
            text=text,
            variable=var,
            font=("Segoe UI", 10),
            checkbox_width=16,
            checkbox_height=16,
            checkmark_color=C_ACCENT,
            border_color=C_SUBTLE,
            hover_color=C_HOVER,
        ).pack(side="left")
        qmark(row, tip_key).pack(side="left", padx=(4, 0))

    def _dd(
        self,
        parent,
        label: str,
        values: list[str],
        var: ctk.StringVar,
        tip_key: str,
        width: int = 110,
    ):
        row = self._row(parent)
        ctk.CTkLabel(row, text=label, font=("Segoe UI", 10)).pack(side="left")
        qmark(row, tip_key).pack(side="left", padx=(4, 0))
        ctk.CTkOptionMenu(
            row,
            values=values,
            variable=var,
            width=width,
            height=26,
            font=("Segoe UI", 10),
            fg_color=C_HOVER,
            button_color=C_BORDER,
            dropdown_fg_color=C_CARD,
        ).pack(side="right")

    def _build_adv(self, p):
        # Checkboxes.
        self._prog = tk.BooleanVar(value=True)
        self._opt = tk.BooleanVar(value=True)
        self._gray = tk.BooleanVar(value=False)
        self._cb(p, "Progressive JPEG", self._prog, "progressive")
        self._cb(p, "Optimize Huffman", self._opt, "optimize")
        self._cb(p, "Grayscale", self._gray, "grayscale")

        # Option menus.
        self._chroma = ctk.StringVar(value="2x2 (4:2:0)")
        self._dct = ctk.StringVar(value="int")
        self._quant = ctk.StringVar(value="0")
        self._dd(
            p,
            "Subsampling",
            ["2x2 (4:2:0)", "2x1 (4:2:2)", "1x1 (4:4:4)"],
            self._chroma,
            "chroma",
            132,
        )
        self._dd(p, "DCT method", ["int", "float", "fast"], self._dct, "dct", 80)
        self._dd(
            p,
            "Quantization table",
            [str(i) for i in range(9)],
            self._quant,
            "quant_table",
            60,
        )

        # Smoothing slider.
        row = self._row(p)
        ctk.CTkLabel(row, text="Smoothing", font=("Segoe UI", 10)).pack(side="left")
        qmark(row, "smooth").pack(side="left", padx=(4, 0))
        self._slbl = ctk.CTkLabel(row, text="0", font=("Segoe UI", 10), width=24)
        self._slbl.pack(side="right")

        self._sslider = ctk.CTkSlider(
            p,
            from_=0,
            to=100,
            height=16,
            button_color=C_ACCENT,
            progress_color=C_ACCENT,
            command=lambda v: self._slbl.configure(text=str(int(v))),
        )
        self._sslider.set(0)
        self._sslider.pack(fill="x", padx=10, pady=(0, 10))

    def _toggle_adv(self):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill="x", pady=(0, 6))
            self._adv_btn.configure(text="▼   Advanced settings")
        else:
            self._adv_frame.pack_forget()
            self._adv_btn.configure(text="▶   Advanced settings")

    def get(self) -> dict:
        """Return the current compression options in the worker's expected format."""
        chroma_map = {
            "2x2 (4:2:0)": "2x2",
            "2x1 (4:2:2)": "2x1",
            "1x1 (4:4:4)": "1x1",
        }
        return {
            "quality": int(self._qslider.get()),
            "progressive": self._prog.get(),
            "optimize": self._opt.get(),
            "grayscale": self._gray.get(),
            "chroma": chroma_map.get(self._chroma.get(), "2x2"),
            "dct": self._dct.get(),
            "quant_table": int(self._quant.get()),
            "smooth": int(self._sslider.get()),
        }


# ─── Main application ─────────────────────────────────────────────────────────


class App(ctk.CTk):
    """Main application window coordinating file selection, processing, and views."""

    def __init__(self):
        super().__init__()
        self.title("MozJPEG Compressor")
        self.geometry("1160x740")
        self.minsize(900, 620)
        self.configure(fg_color=C_BG)

        self._cjpeg: Path | None = find_cjpeg()
        self._source_dir: Path | None = None
        self._tasks: list[tuple[Path, Path]] = []  # (input, output)
        self._iid_map: dict[Path, str] = {}  # input → treeview iid
        self._iid_to_inp: dict[str, Path] = {}  # iid → input
        self._results: dict[Path, dict] = {}
        self._worker: Compressor | None = None
        # Files currently marked for compression.
        self._selected_files: set[Path] = set()

        self._build_ui()

        if not self._cjpeg:
            self.after(500, self._prompt_download)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header.
        hdr = ctk.CTkFrame(self, fg_color=C_SURFACE, corner_radius=0)
        hdr.pack(fill="x")

        ctk.CTkLabel(
            hdr,
            text="MozJPEG Compressor",
            font=("Segoe UI", 14, "bold"),
            text_color=C_TEXT,
        ).pack(side="left", padx=20, pady=10)

        self._chip = ctk.CTkLabel(
            hdr,
            text="✓  MozJPEG ready" if self._cjpeg else "⚠  MozJPEG not installed",
            font=("Segoe UI", 12),
            text_color=C_OK if self._cjpeg else C_WARN,
        )
        self._chip.pack(side="right", padx=20)

        mid = ctk.CTkFrame(hdr, fg_color=C_CARD, corner_radius=8)
        mid.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        frow = ctk.CTkFrame(mid, fg_color="transparent")
        frow.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(
            frow,
            text="Source folder",
            font=("Segoe UI", 9),
            text_color=C_MUTED,
        ).pack(side="left", padx=(0, 8))
        self._folder_lbl = ctk.CTkLabel(
            frow,
            text="No folder selected",
            font=("Segoe UI", 9),
            text_color=C_MUTED,
            anchor="w",
        )
        self._folder_lbl.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            frow,
            text="📁",
            width=30,
            height=26,
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=("Segoe UI", 12),
            command=self._browse,
        ).pack(side="right")

        rec_row = ctk.CTkFrame(mid, fg_color="transparent")
        rec_row.pack(fill="x", padx=10, pady=(2, 6))
        self._recursive = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            rec_row,
            text="Include subfolders",
            variable=self._recursive,
            font=("Segoe UI", 10),
            checkbox_width=16,
            checkbox_height=16,
            checkmark_color=C_ACCENT,
            border_color=C_SUBTLE,
            hover_color=C_HOVER,
        ).pack(side="left")
        qmark(rec_row, "recursive").pack(side="left", padx=(4, 0))

        # Corpo principal
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent", width=290)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)
        self._build_left(left)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=2)
        right.rowconfigure(1, weight=3)
        right.rowconfigure(2, weight=0)
        right.columnconfigure(0, weight=1)
        self._build_right(right)

    def _build_left(self, parent):
        # ── Output file card ──────────────────────────────────────────────────
        out_card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        out_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            out_card,
            text="Output file",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self._suf_mode = tk.StringVar(value="auto")
        for val, label in [
            ("auto", "Automatic suffix  (_compressed_80)"),
            ("custom", "Custom suffix"),
            ("none", "No suffix  (original name)"),
        ]:
            ctk.CTkRadioButton(
                out_card,
                text=label,
                value=val,
                variable=self._suf_mode,
                font=("Segoe UI", 10),
                radiobutton_width=16,
                radiobutton_height=16,
                fg_color=C_ACCENT,
                border_color=C_SUBTLE,
                hover_color=C_HOVER,
                command=self._toggle_suffix,
            ).pack(anchor="w", padx=14, pady=(0, 2))

        self._suf_entry = ctk.CTkEntry(
            out_card,
            placeholder_text="ex: _web  ou  _tbp",
            font=("Segoe UI", 10),
            height=28,
            fg_color=C_HOVER,
            border_color=C_BORDER,
            state="disabled",
        )
        self._suf_entry.pack(fill="x", padx=14, pady=(4, 2))

        self._suf_preview = ctk.CTkLabel(
            out_card,
            text="->  name_compressed_80.jpg",
            font=("Segoe UI", 8),
            text_color=C_MUTED,
            anchor="w",
        )
        self._suf_preview.pack(fill="x", padx=14, pady=(0, 6))

        open_row = ctk.CTkFrame(out_card, fg_color="transparent")
        open_row.pack(fill="x", padx=14, pady=(0, 12))
        self._open_export = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            open_row,
            text="Open export folder when finished",
            variable=self._open_export,
            font=("Segoe UI", 10),
            checkbox_width=16,
            checkbox_height=16,
            checkmark_color=C_ACCENT,
            border_color=C_SUBTLE,
            hover_color=C_HOVER,
        ).pack(side="left")

        # ── Processing options card ───────────────────────────────────────────
        proc_card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        proc_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            proc_card,
            text="Processing",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Minimum file size.
        ms_row = ctk.CTkFrame(proc_card, fg_color="transparent")
        ms_row.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(ms_row, text="Skip below", font=("Segoe UI", 10)).pack(
            side="left"
        )
        qmark(ms_row, "min_size").pack(side="left", padx=(4, 0))
        ctk.CTkLabel(ms_row, text="KB", font=("Segoe UI", 10), text_color=C_MUTED).pack(
            side="right"
        )
        self._min_size_entry = ctk.CTkEntry(
            ms_row,
            width=64,
            height=26,
            font=("Segoe UI", 10),
            fg_color=C_HOVER,
            border_color=C_BORDER,
        )
        self._min_size_entry.insert(0, "100")
        self._min_size_entry.pack(side="right", padx=(0, 4))

        # Resize options.
        rs_row = ctk.CTkFrame(proc_card, fg_color="transparent")
        rs_row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(rs_row, text="Resize", font=("Segoe UI", 10)).pack(
            side="left"
        )
        qmark(rs_row, "resize").pack(side="left", padx=(4, 0))

        self._resize_var = ctk.StringVar(value="Do not resize")
        ctk.CTkOptionMenu(
            proc_card,
            values=[
                "Do not resize",
                "75% of original",
                "50% of original",
                "25% of original",
                "Longest side (px)...",
            ],
            variable=self._resize_var,
            width=234,
            height=28,
            font=("Segoe UI", 10),
            fg_color=C_HOVER,
            button_color=C_BORDER,
            dropdown_fg_color=C_CARD,
            command=self._on_resize_change,
        ).pack(fill="x", padx=14, pady=(4, 0))

        px_row = ctk.CTkFrame(proc_card, fg_color="transparent")
        px_row.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkLabel(
            px_row, text="Longest side:", font=("Segoe UI", 10), text_color=C_MUTED
        ).pack(side="left")
        ctk.CTkLabel(px_row, text="px", font=("Segoe UI", 10), text_color=C_MUTED).pack(
            side="right"
        )
        self._resize_px_entry = ctk.CTkEntry(
            px_row,
            width=74,
            height=26,
            font=("Segoe UI", 10),
            fg_color=C_HOVER,
            border_color=C_BORDER,
            state="disabled",
        )
        self._resize_px_entry.insert(0, "2000")
        self._resize_px_entry.pack(side="right", padx=(0, 4))

        # ── Compression settings ──────────────────────────────────────────────
        self._settings = SettingsPanel(parent)
        self._settings.pack(fill="x", pady=(0, 8))

        # ── Action buttons ─────────────────────────────────────────────────────
        btns = ctk.CTkFrame(parent, fg_color="transparent")
        btns.pack(fill="x")
        for column in range(3):
            btns.columnconfigure(column, weight=1)

        self._btn_scan = ctk.CTkButton(
            btns,
            text="🔍\nFind files",
            font=("Segoe UI", 9),
            width=78,
            height=78,
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            command=self._scan,
        )
        self._btn_scan.grid(row=0, column=0, padx=(0, 4), sticky="nsew")

        self._btn_start = ctk.CTkButton(
            btns,
            text="▶\nStart\ncompression",
            font=("Segoe UI", 9, "bold"),
            width=78,
            height=78,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color="#fff",
            command=self._start,
            state="disabled",
        )
        self._btn_start.grid(row=0, column=1, padx=2, sticky="nsew")

        self._btn_stop = ctk.CTkButton(
            btns,
            text="⏹\nStop",
            font=("Segoe UI", 9),
            width=78,
            height=78,
            fg_color="#2a1010",
            hover_color="#3a1818",
            text_color=C_ERR,
            command=self._stop,
            state="disabled",
        )
        self._btn_stop.grid(row=0, column=2, padx=(4, 0), sticky="nsew")

    def _build_right(self, parent):
        # File-list card.
        list_card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10)
        list_card.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        list_card.rowconfigure(2, weight=1)
        list_card.columnconfigure(0, weight=1)

        hdr_row = ctk.CTkFrame(list_card, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(hdr_row, text="Files", font=("Segoe UI", 11, "bold")).pack(
            side="left"
        )
        self._zoom_frame = ctk.CTkFrame(hdr_row, fg_color="transparent")
        # Hidden until grid view is enabled.
        self._thumb_size = 100
        ctk.CTkButton(
            self._zoom_frame,
            text="−",
            width=24,
            height=24,
            font=("Segoe UI", 11),
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            command=lambda: self._zoom_grid(-20),
        ).pack(side="left", padx=(0, 2))
        self._zoom_lbl = ctk.CTkLabel(
            self._zoom_frame,
            text="100px",
            width=44,
            font=("Segoe UI", 9),
            text_color=C_MUTED,
        )
        self._zoom_lbl.pack(side="left")
        ctk.CTkButton(
            self._zoom_frame,
            text="+",
            width=24,
            height=24,
            font=("Segoe UI", 11),
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            command=lambda: self._zoom_grid(+20),
        ).pack(side="left", padx=(2, 8))

        # Selection buttons.
        sel_frame = ctk.CTkFrame(hdr_row, fg_color="transparent")
        sel_frame.pack(side="left", padx=(16, 0))

        ctk.CTkButton(
            sel_frame,
            text="Select all",
            width=120,
            height=24,
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=("Segoe UI", 9),
            command=self._select_all,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            sel_frame,
            text="Invert selection",
            width=110,
            height=24,
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=("Segoe UI", 9),
            command=self._invert_selection,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            sel_frame,
            text="Clear selection",
            width=110,
            height=24,
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=("Segoe UI", 9),
            command=self._select_none,
        ).pack(side="left", padx=2)

        self._view_btn = ctk.CTkButton(
            hdr_row,
            text="⊞  Grid",
            width=76,
            height=24,
            font=("Segoe UI", 9),
            fg_color=C_HOVER,
            hover_color=C_BORDER,
            text_color=C_MUTED,
            command=self._toggle_view,
        )
        self._view_btn.pack(side="right")
        self._view_mode = "list"

        # Progresso
        prog_row = ctk.CTkFrame(list_card, fg_color="transparent")
        prog_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        self._prog_bar = ctk.CTkProgressBar(prog_row, progress_color=C_ACCENT)
        self._prog_bar.set(0)
        self._prog_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._prog_lbl = ctk.CTkLabel(
            prog_row,
            text="0 / 0",
            font=("Segoe UI", 9),
            text_color=C_MUTED,
            width=60,
        )
        self._prog_lbl.pack(side="right")

        # Treeview
        tree_outer = tk.Frame(list_card, bg=C_BG)
        tree_outer.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "M.Treeview",
            background=C_BG,
            foreground=C_TEXT,
            fieldbackground=C_BG,
            rowheight=27,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "M.Treeview.Heading",
            background=C_SURFACE,
            foreground=C_MUTED,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "M.Treeview",
            background=[("selected", "#22223a")],
            foreground=[("selected", C_TEXT)],
        )
        style.configure(
            "M.Vertical.TScrollbar",
            background=C_HOVER,
            troughcolor=C_BG,
            bordercolor=C_BG,
            arrowcolor=C_MUTED,
        )

        self._list_outer = tk.Frame(tree_outer, bg=C_BG)
        self._list_outer.pack(fill="both", expand=True)
        self._tree = ttk.Treeview(
            self._list_outer,
            columns=("sel", "file", "orig", "comp", "saved", "state"),
            show="headings",
            style="M.Treeview",
            selectmode="browse",
        )
        for col, label, width, anchor in [
            ("sel", "Select", 40, "center"),
            ("file", "File", 300, "w"),
            ("orig", "Original", 88, "e"),
            ("comp", "Compressed", 96, "e"),
            ("saved", "Saved", 72, "e"),
            ("state", "Status", 116, "w"),
        ]:
            self._tree.heading(col, text=label, anchor=anchor)
            self._tree.column(col, width=width, minwidth=width, stretch=False, anchor=anchor)

        self._tree.tag_configure("done", foreground=C_OK)
        self._tree.tag_configure("error", foreground=C_ERR)
        self._tree.tag_configure("skipped", foreground=C_MUTED)
        self._tree.tag_configure("processing", foreground=C_ACCENT)
        self._tree.tag_configure("pending", foreground=C_MUTED)
        self._tree.tag_configure("selected", background=C_SELECTED)

        vsb = ttk.Scrollbar(
            self._list_outer,
            orient="vertical",
            command=self._tree.yview,
            style="M.Vertical.TScrollbar",
        )
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Grid-view container.
        self._grid_outer = tk.Frame(tree_outer, bg=C_BG)
        self._grid_canvas = tk.Canvas(
            self._grid_outer, bg=C_BG, bd=0, highlightthickness=0
        )
        self._grid_vsb = ttk.Scrollbar(
            self._grid_outer,
            orient="vertical",
            command=self._grid_canvas.yview,
            style="M.Vertical.TScrollbar",
        )
        self._grid_canvas.configure(yscrollcommand=self._grid_vsb.set)
        self._grid_inner = tk.Frame(self._grid_canvas, bg=C_BG)
        self._gwin = self._grid_canvas.create_window(
            (0, 0), window=self._grid_inner, anchor="nw"
        )
        self._grid_inner.bind(
            "<Configure>",
            lambda e: self._grid_canvas.configure(
                scrollregion=self._grid_canvas.bbox("all")
            ),
        )
        self._grid_canvas.bind("<Configure>", self._on_grid_configure)

        self._grid_canvas.bind(
            "<MouseWheel>",
            lambda e: self._grid_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )
        self._grid_photos: dict = {}
        self._grid_cells: dict = {}
        self._grid_selected: Path | None = None
        self._grid_generation = 0

        # Preview panel.
        self._preview = PreviewPanel(parent, fg_color=C_CARD, corner_radius=10)
        self._preview.grid(row=1, column=0, sticky="nsew")

        # Statistics footer.
        footer = ctk.CTkFrame(parent, fg_color=C_SURFACE, corner_radius=8, height=34)
        footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        footer.grid_propagate(False)
        self._stat_lbl = ctk.CTkLabel(
            footer,
            text="No data yet.",
            font=("Segoe UI", 9),
            text_color=C_MUTED,
        )
        self._stat_lbl.pack(side="left", padx=14)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askdirectory(title="Select source folder")
        if path:
            self._source_dir = Path(path)
            self._folder_lbl.configure(text=str(self._source_dir), text_color=C_TEXT)

    def _toggle_suffix(self):
        mode = self._suf_mode.get()
        self._suf_entry.configure(state="normal" if mode == "custom" else "disabled")
        q = int(self._settings._qslider.get())
        previews = {
            "auto": f"->  name_compressed_{q}.jpg",
            "custom": "->  name<suffix>.jpg",
            "none": "->  name.jpg  (original name)",
        }
        self._suf_preview.configure(text=previews[mode])

    def _on_resize_change(self, val: str):
        if val == "Longest side (px)...":
            self._resize_px_entry.configure(state="normal")
        else:
            self._resize_px_entry.configure(state="disabled")

    def _output_path(self, inp: Path, quality: int) -> Path:
        """Build an output path from the current suffix mode and image location."""
        mode = self._suf_mode.get()
        if mode == "custom":
            suffix = self._suf_entry.get().strip() or f"_compressed_{quality}"
            filename = f"{inp.stem}{suffix}.jpg"
        elif mode == "none":
            filename = f"{inp.stem}.jpg"
        else:
            filename = f"{inp.stem}_compressed_{quality}.jpg"
        return self._source_dir / EXPORT_FOLDER / inp.relative_to(self._source_dir).parent / filename

    def _toggle_view(self):
        """Switch between the tree list and thumbnail grid views."""
        if self._view_mode == "list":
            self._view_mode = "grid"
            self._list_outer.pack_forget()
            self._grid_vsb.pack(side="right", fill="y")
            self._grid_canvas.pack(side="left", fill="both", expand=True)
            self._grid_outer.pack(fill="both", expand=True)
            self._view_btn.configure(text="☰  Lista")
            self._zoom_frame.pack(side="right", padx=(0, 6))
            self._populate_grid()
        else:
            self._view_mode = "list"
            self._grid_outer.pack_forget()
            self._zoom_frame.pack_forget()
            self._list_outer.pack(fill="both", expand=True)
            self._view_btn.configure(text="⊞  Grid")

    def _populate_grid(self):
        """Rebuild grid cells and start asynchronous thumbnail loading.

        Every rebuild increments ``_grid_generation``. Workers from an older
        rebuild may finish later, so their callbacks must not update destroyed
        labels.
        """
        self._grid_generation += 1
        generation = self._grid_generation
        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._grid_photos.clear()
        self._grid_cells.clear()

        tw = self._thumb_size
        th = int(tw * 0.72)
        cell_w = tw + 24
        COLS = max(2, min(8, int(self._grid_canvas.winfo_width() / (cell_w + 10)) or 4))
        COLS, CELL_W, THUMB_W, THUMB_H = COLS, cell_w, tw, th

        for idx, (inp, out) in enumerate(self._tasks):
            col = idx % COLS
            row = idx // COLS
            self._grid_inner.columnconfigure(col, weight=0)

            cell = ctk.CTkFrame(
                self._grid_inner,
                fg_color=C_CARD,
                border_color=C_BORDER,
                border_width=1,
                width=CELL_W,
                height=th + 54,
                corner_radius=0,
            )
            cell.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            cell.grid_propagate(False)

            img_lbl = tk.Label(cell, bg=C_CARD, cursor="hand2")
            img_lbl.pack(pady=(6, 2))

            usable = int(cell_w * 0.95)
            avg_char_px = 5.5  # Segoe UI 8pt
            max_chars = max(8, int(usable / avg_char_px))
            name = (
                inp.name
                if len(inp.name) <= max_chars
                else inp.name[: max_chars - 1] + "…"
            )
            name_lbl = tk.Label(
                cell,
                text=name,
                bg=C_CARD,
                fg=C_TEXT,
                font=("Segoe UI", 8),
                width=0,
            )
            name_lbl.pack(fill="x", padx=int(cell_w * 0.025))

            skip = out.exists()
            st_lbl = tk.Label(
                cell,
                text="Skipped" if skip else "Pending",
                bg=C_CARD,
                fg=C_WARN if skip else C_MUTED,
                font=("Segoe UI", 7),
            )
            st_lbl.pack()

            # Checkmark in the upper-right corner.
            check_lbl = tk.Label(
                cell,
                text="",
                bg=C_CARD,
                fg=C_ACCENT,
                font=("Segoe UI", 12),
                width=2,
                height=1,
            )
            check_lbl.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)

            for w in (cell, img_lbl, name_lbl, st_lbl, check_lbl):
                w.bind("<Button-1>", lambda e, i=inp: self._grid_select(i, e))

            # Update the checkmark later without rebuilding the cell.
            self._grid_cells[inp] = {"status": st_lbl, "cell": cell, "check_lbl": check_lbl}

            threading.Thread(
                target=self._load_thumb,
                args=(inp, img_lbl, THUMB_W, THUMB_H, generation),
                daemon=True,
            ).start()

        self._refresh_all_selection_visuals()

    def _load_thumb(
        self, inp: Path, lbl: tk.Label, tw: int, th: int, generation: int
    ):
        """Load one thumbnail off-thread and apply it only if still current."""
        try:
            img = Image.open(inp)
            img.thumbnail((tw, th), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            def apply_thumbnail():
                if generation != self._grid_generation or not lbl.winfo_exists():
                    return
                self._grid_photos[inp] = photo
                lbl.configure(image=photo)

            self.after(0, apply_thumbnail)
        except Exception:
            def apply_error():
                if generation != self._grid_generation or not lbl.winfo_exists():
                    return
                lbl.configure(text="⚠", fg=C_MUTED, font=("Segoe UI", 18))

            self.after(0, apply_error)

    def _zoom_grid(self, delta: int):
        self._thumb_size = max(60, min(240, self._thumb_size + delta))
        self._zoom_lbl.configure(text=f"{self._thumb_size}px")
        self._populate_grid()

    def _grid_select(self, inp: Path, event=None):
        """Select a grid item, update preview content, and refresh its visuals."""
        iid = self._iid_map.get(inp)
        if iid:
            self._tree.unbind("<<TreeviewSelect>>")
            self._tree.selection_set(iid)
            self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # CTRL/Shift selection handling.
        if event:
            ctrl_held = event.state & 0x4
            shift_held = event.state & 0x1

            if (
                shift_held
                and hasattr(self, "_last_clicked_file")
                and self._last_clicked_file
            ):
                self._select_range(self._last_clicked_file, inp)
            elif ctrl_held:
                self._toggle_file_selection(inp)
            else:
                self._toggle_file_selection(inp)
        else:
            # Programmatic call without an event: toggle the item.
            self._toggle_file_selection(inp)

        # Remember this item for the next Shift-click.
        self._last_clicked_file = inp

        res = self._results.get(inp)
        comp = res["out"] if res and res["status"] == "done" else None
        self._preview.load(inp, comp)

        # Update only the previous and current preview cells.
        if self._grid_selected and self._grid_selected in self._grid_cells:
            self._grid_cells[self._grid_selected]["cell"].configure(
                border_color=C_BORDER
            )
        if inp in self._grid_cells:
            self._grid_cells[inp]["cell"].configure(border_color=C_ACCENT)
        self._grid_selected = inp

    def _on_grid_configure(self, e):
        current = self._grid_canvas.itemcget(self._gwin, "width")
        if str(int(e.width)) != str(int(float(current) if current else 0)):
            self._grid_canvas.itemconfig(self._gwin, width=e.width)

    def _refresh_grid_cell(self, inp: Path, result: dict):
        c = self._grid_cells.get(inp)
        if not c:
            return
        if result["status"] == "done":
            c["status"].configure(text=f"✓ −{result['pct']:.1f}%", fg=C_OK)
        elif result["status"] == "error":
            c["status"].configure(text="✗ Erro", fg=C_ERR)

    def _scan(self):
        """Discover source images and create the initial task/output-path list."""
        if not self._source_dir:
            messagebox.showwarning("No folder", "Select a folder first.")
            return

        export_dir = self._source_dir / EXPORT_FOLDER
        pattern = "**/*" if self._recursive.get() else "*"
        try:
            min_bytes = int(self._min_size_entry.get() or 100) * 1024
        except ValueError:
            min_bytes = 100 * 1024

        files = sorted(
            [
                p
                for p in self._source_dir.glob(pattern)
                if p.is_file()
                and p.suffix.lower() in SUPPORTED
                and not str(p.resolve()).startswith(str(export_dir.resolve()))
                and p.stat().st_size >= min_bytes
            ]
        )

        quality = self._settings.get()["quality"]
        self._tasks = []
        for f in files:
            self._tasks.append((f, self._output_path(f, quality)))

        self._results = {}
        
        n = len(self._tasks)
        self._prog_lbl.configure(text=f"0 / {n}")
        self._prog_bar.set(0)
        self._btn_start.configure(state="normal" if n > 0 else "disabled")

        if n == 0:
            messagebox.showinfo(
                "No files",
                "No JPEG or PNG files were found in the selected folder.",
            )

        self._selected_files.clear()
        self._last_clicked_file = None

        # Rebuild the list once after preparing selection state.
        self._populate_tree()

    def _populate_tree(self):
        """Synchronize the list view with the current task and result state."""
        self._tree.delete(*self._tree.get_children())
        self._iid_map.clear()
        self._iid_to_inp.clear()

        for inp, out in self._tasks:
            skip = out.exists()
            tag = "skipped" if skip else "pending"
            state = "Skipped" if skip else "Pending"
            try:
                orig_sz = fmt_size(inp.stat().st_size)
            except OSError:
                orig_sz = "?"

            iid = self._tree.insert(
                "",
                "end",
                values=("", inp.name, orig_sz, "—", "—", state),
                tags=(tag,),
            )
            self._iid_map[inp] = iid
            self._iid_to_inp[iid] = inp

        if self._view_mode == "grid":
            self._populate_grid()

        self._refresh_all_selection_visuals()

    def _start(self):
        """Start compression for selected, non-existing outputs."""
        if not self._cjpeg:
            messagebox.showerror("MozJPEG not installed", "Install MozJPEG first.")
            return
        if not self._tasks:
            messagebox.showinfo(
                "No files", "Click 'Find files' first."
            )
            return

        quality = self._settings.get()["quality"]
        self._tasks = [
            (inp, self._output_path(inp, quality)) for inp, _ in self._tasks
        ]

        # Keep only selected files whose outputs do not already exist.
        active = [
            (inp, out)
            for inp, out in self._tasks
            if not out.exists() and inp in self._selected_files
        ]

        if not active:
            # Distinguish between no selection and already-existing outputs.
            any_selected = any(inp in self._selected_files for inp, _ in self._tasks)
            if not any_selected:
                messagebox.showwarning(
                    "No files selected",
                    "Select at least one file to compress.",
                )
            else:
                messagebox.showinfo(
                    "Nothing to do",
                    "All selected files already exist in the export folder.\n"
                    "Change the quality and click 'Find files' to generate new ones.",
                )
            return

        # Mark unprocessed files as skipped in the tree view.
        for inp, out in self._tasks:
            if (inp, out) not in active:
                iid = self._iid_map.get(inp)
                if iid:
                    # Determine why this file was skipped.
                    if out.exists():
                        reason = "already exists"
                    else:
                        reason = "not selected"

                    self._tree.set(iid, "orig", "—")
                    self._tree.set(iid, "comp", "—")
                    self._tree.set(iid, "saved", "—")
                    self._tree.set(iid, "state", reason)
                    self._tree.item(iid, tags=("skipped",))

        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._btn_scan.configure(state="disabled")
        settings = self._settings.get()
        rv = self._resize_var.get()
        if rv == "Do not resize":
            settings["resize_mode"] = "none"
        elif rv == "Longest side (px)...":
            settings["resize_mode"] = "custom"
            try:
                settings["resize_px"] = int(self._resize_px_entry.get() or 2000)
            except ValueError:
                settings["resize_px"] = 2000
        else:
            settings["resize_mode"] = rv.split("%")[0].strip()  # "75", "50", "25"
        self._worker = Compressor(
            cjpeg=self._cjpeg,
            tasks=active,
            settings=settings,
            on_file_done=self._on_file_done,
            on_progress=self._on_progress,
            on_finish=self._on_finish,
        )
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self._btn_stop.configure(state="disabled")

    def _select_all(self):
        """Select every file in the current task list."""
        self._selected_files = {inp for inp, _ in self._tasks}
        self._refresh_all_selection_visuals()

    def _select_none(self):
        """Clear the current file selection."""
        self._selected_files.clear()
        self._refresh_all_selection_visuals()

    def _invert_selection(self):
        """Invert the current file selection."""
        all_files = {inp for inp, _ in self._tasks}
        self._selected_files = all_files - self._selected_files
        self._refresh_all_selection_visuals()

    def _toggle_file_selection(self, inp: Path):
        """Toggle selection for one file."""
        if inp in self._selected_files:
            self._selected_files.discard(inp)
        else:
            self._selected_files.add(inp)
        self._refresh_file_visual(inp)

    def _select_range(self, start_inp: Path, end_inp: Path):
        """Select every file between the start and end items, inclusive."""
        # Find indices in the ordered task list.
        task_paths = [inp for inp, _ in self._tasks]
        try:
            start_idx = task_paths.index(start_inp)
            end_idx = task_paths.index(end_inp)
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx

            # Add every item in the range to the selection.
            for inp in task_paths[start_idx : end_idx + 1]:
                self._selected_files.add(inp)

            self._refresh_all_selection_visuals()
        except ValueError:
            pass  # Ignore files that are no longer present in the task list.

    def _refresh_all_selection_visuals(self):
        """Refresh selection indicators for every file in both views."""
        for inp, _ in self._tasks:
            self._refresh_file_visual(inp)

    def _refresh_file_visual(self, inp: Path):
        """Update selection indicators in both list and grid representations."""
        is_selected = inp in self._selected_files

        # Update the tree view (list mode).
        if inp in self._iid_map:
            iid = self._iid_map[inp]
            # Apply the selected background tag.
            if is_selected:
                self._tree.item(iid, tags=("selected",))
            else:
                # Restore the original tag when a result is available.
                result = self._results.get(inp)
                if result:
                    status = result.get("status", "pending")
                    self._tree.item(iid, tags=(status,))

            # Update the checkmark column.
            check = "✓" if is_selected else ""
            self._tree.set(iid, "sel", check)

        # Update the grid cell (grid mode).
        if inp in self._grid_cells:
            cell_frame = self._grid_cells[inp]["cell"]
            # Update the border and background.
            if is_selected:
                cell_frame.configure(
                    border_width=2, border_color=C_ACCENT, fg_color=C_SELECTED
                )
            else:
                cell_frame.configure(
                    border_width=1, border_color=C_BORDER, fg_color=C_CARD
                )

            # Update the checkmark label.
            if "check_lbl" in self._grid_cells[inp]:
                check_lbl = self._grid_cells[inp]["check_lbl"]
                check_lbl.configure(text="✓" if is_selected else "")

    # ── Worker callbacks (called from a background thread) ───────────────────

    def _on_file_done(self, inp: Path, result: dict):
        """Store a worker result and schedule its UI update on the Tk thread."""
        self._results[inp] = result
        self.after(0, self._update_row, inp, result)

    def _on_progress(self, done: int, total: int, current: Path):
        """Forward worker progress safely to the Tk event loop."""
        self.after(0, self._set_progress, done, total, current)

    def _on_finish(self):
        """Schedule the final progress and statistics update on the Tk thread."""
        self.after(0, self._finish_ui)

    def _update_row(self, inp: Path, result: dict):
        """Render one completed or failed compression result in the UI."""
        iid = self._iid_map.get(inp)
        if not iid:
            return
        if result["status"] == "done":
            self._tree.item(
                iid,
                values=(
                    "",
                    inp.name,
                    fmt_size(result["orig"]),
                    fmt_size(result["comp"]),
                    f"−{result['pct']:.1f}%",
                    "Completed",
                ),
                tags=("done",),
            )
        elif result["status"] == "error":
            try:
                orig_sz = fmt_size(inp.stat().st_size)
            except OSError:
                orig_sz = "?"
            self._tree.item(
                iid,
                values=(
                    "",
                    inp.name,
                    orig_sz,
                    "—",
                    "—",
                    "Error",
                ),
                tags=("error",),
            )

        if self._view_mode == "grid":
            self._refresh_grid_cell(inp, result)

    def _set_progress(self, done: int, total: int, current: Path):
        if total:
            self._prog_bar.set(done / total)
        self._prog_lbl.configure(text=f"{done} / {total}")

        iid = self._iid_map.get(current)
        if iid:
            try:
                orig_sz = fmt_size(current.stat().st_size)
            except OSError:
                orig_sz = "?"
            self._tree.item(
                iid,
                values=(
                    "",
                    current.name,
                    orig_sz,
                    "—",
                    "—",
                    "Processing...",
                ),
                tags=("processing",),
            )
            self._tree.see(iid)

    def _finish_ui(self):
        """Re-enable controls and display final counts and saved space."""
        self._prog_bar.set(1.0)
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._btn_scan.configure(state="normal")

        done = sum(1 for r in self._results.values() if r["status"] == "done")
        errs = sum(1 for r in self._results.values() if r["status"] == "error")
        saved = sum(
            r["orig"] - r["comp"]
            for r in self._results.values()
            if r["status"] == "done"
        )

        self._prog_lbl.configure(
            text=f"{done} completed" + (f", {errs} errors" if errs else ""),
        )

        if done:
            self._stat_lbl.configure(
                text=f"✓  {done} file(s) compressed  ·  "
                f"Space saved: {fmt_size(saved)}"
                + (f"  ·  {errs} error(s)" if errs else ""),
                text_color=C_OK,
            )
        else:
            self._stat_lbl.configure(
                text="No files processed.", text_color=C_MUTED
            )

        if self._open_export.get() and self._source_dir and done:
            export_dir = self._source_dir / EXPORT_FOLDER
            if export_dir.exists():
                os.startfile(export_dir)

    # ── List selection ─────────────────────────────────────────────────────────

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        inp = self._iid_to_inp.get(iid)
        if not inp:
            return

        # Show the original and, when available, the compressed file in the preview.
        res = self._results.get(inp)
        comp_path = res["out"] if res and res["status"] == "done" else None
        self._preview.load(inp, comp_path)

        # CTRL/Shift selection handling.
        ctrl_held = event.state & 0x4  # CTRL
        shift_held = event.state & 0x1  # Shift

        if (
            shift_held
            and hasattr(self, "_last_clicked_file")
            and self._last_clicked_file
        ):
            # Range selection
            self._select_range(self._last_clicked_file, inp)
        elif ctrl_held:
            # Toggle individual
            self._toggle_file_selection(inp)

        # Remember this item for the next Shift-click.
        self._last_clicked_file = inp

    # ── MozJPEG download ──────────────────────────────────────────────────────

    def _prompt_download(self):
        DownloadWindow(self, self._on_download_done)

    def _on_download_done(self, success: bool):
        if success:
            self._cjpeg = find_cjpeg()
        ok = bool(self._cjpeg)
        self._chip.configure(
            text="✓  MozJPEG ready" if ok else "✗  MozJPEG not installed",
            text_color=C_OK if ok else C_ERR,
        )
        if not ok:
            messagebox.showerror(
                "MozJPEG not installed",
                "Install it manually from:\n"
                "https://github.com/mozilla/mozjpeg/releases\n\n"
                "After installation, restart the app.",
            )


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
