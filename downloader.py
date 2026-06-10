import os
import zipfile
import time
from datetime import datetime

import pandas as pd
import yt_dlp
import gdown


# =====================
# 文件名（旧版本）
# =====================
def build_filename(row):
    return " ".join([
        str(row["code"]).strip(),
        str(row["version"]).strip(),
        str(row["video"]).strip(),
        str(row["language"]).strip(),
        str(row["size"]).strip(),
        str(row["game"]).strip()
    ])


# =====================
# gdrive下载（简单版）
# =====================
def download_gdrive(url, out):

    gdown.download(url, out, quiet=False)


# =====================
# 主流程
# =====================
def process_excel(excel_path, output_dir, on_progress=None):

    download_dir = os.path.join(output_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)

    df = pd.read_excel(excel_path)

    total = len(df)

    downloaded = []
    failed = []

    for i, row in df.iterrows():

        filename = build_filename(row)
        url = str(row["url"]).strip()

        if on_progress:
            on_progress({
                "type": "item_start",
                "current": i + 1,
                "total": total,
                "filename": filename
            })

        try:

            path = os.path.join(download_dir, filename + ".mp4")

            # TikTok / yt-dlp
            if "tiktok" in url:
                ydl_opts = {
                    "outtmpl": path,
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

            # Google Drive
            elif "drive.google" in url:
                download_gdrive(url, path)

            else:
                raise Exception("unsupported url")

            downloaded.append(path)

            if on_progress:
                on_progress({
                    "type": "item_done",
                    "filename": filename,
                    "success": True
                })

        except Exception:

            failed.append(filename)

            if on_progress:
                on_progress({
                    "type": "item_done",
                    "filename": filename,
                    "success": False
                })

        time.sleep(0.5)

    # =====================
    # ZIP生成
    # =====================
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(output_dir, f"videos_{ts}.zip")

    with zipfile.ZipFile(zip_path, "w") as z:
        for f in downloaded:
            if os.path.exists(f):
                z.write(f, os.path.basename(f))

    if on_progress:
        on_progress({
            "type": "complete",
            "result": {
                "zip_path": zip_path,
                "downloaded_count": len(downloaded),
                "failed_count": len(failed)
            }
        })

    return zip_path