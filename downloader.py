import os
import re
import zipfile
from datetime import datetime
from typing import Callable, Optional

import pandas as pd
import yt_dlp
import gdown


def clean_text(text: str) -> str:
    return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", str(text))


def build_filename(row) -> str:
    code = str(row["code"]).strip()
    version = str(row["version"]).strip()
    video = str(row["video"]).strip()
    language = str(row["language"]).strip()
    size = str(row["size"]).strip()
    game = str(row["game"]).strip()
    return f"{code} {version} {video} {language} {size} {game}"


ProgressCallback = Callable[[dict], None]


def process_excel(
    excel_path: str,
    output_dir: str,
    on_progress: Optional[ProgressCallback] = None,
) -> dict:
    """
    Read Excel, download videos, create ZIP and failed report.

    Returns dict with keys: zip_path, failed_path, downloaded_count, failed_count, failed
    """
    downloads_dir = os.path.join(output_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_excel(excel_path)
    total = len(df)
    downloaded_files = []
    failed = []

    def emit(event: dict):
        if on_progress:
            on_progress(event)

    for index, row in df.iterrows():
        filename = build_filename(row)
        url = str(row["url"]).strip()

        emit(
            {
                "type": "item_start",
                "current": index + 1,
                "total": total,
                "filename": filename,
                "url": url,
            }
        )

        try:
            if "tiktok" in url.lower():
                ydl_opts = {
                    "outtmpl": f"{downloads_dir}/{filename}.%(ext)s",
                    "quiet": True,
                    "no_warnings": True,
                }

                before_files = set(os.listdir(downloads_dir))

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                after_files = set(os.listdir(downloads_dir))
                new_files = after_files - before_files

                for file in new_files:
                    downloaded_files.append(os.path.join(downloads_dir, file))

            elif "drive.google" in url.lower():
                output_file = f"{downloads_dir}/{filename}.mp4"

                gdown.download(url, output_file, quiet=False)

                downloaded_files.append(output_file)

            else:
                raise Exception("不支持的链接类型")

            emit(
                {
                    "type": "item_done",
                    "current": index + 1,
                    "total": total,
                    "filename": filename,
                    "success": True,
                }
            )

        except Exception as e:
            reason = clean_text(str(e))
            failed.append({"filename": filename, "url": url, "reason": reason})

            emit(
                {
                    "type": "item_done",
                    "current": index + 1,
                    "total": total,
                    "filename": filename,
                    "success": False,
                    "reason": reason,
                }
            )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(output_dir, f"videos_{timestamp}.zip")

    emit({"type": "zip_start", "total": total})

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in downloaded_files:
            if os.path.exists(file_path):
                zipf.write(file_path, arcname=os.path.basename(file_path))

    failed_path = None
    if failed:
        failed_path = os.path.join(output_dir, f"failed_{timestamp}.xlsx")
        pd.DataFrame(failed).to_excel(failed_path, index=False)

    result = {
        "zip_path": zip_path,
        "failed_path": failed_path,
        "downloaded_count": len(downloaded_files),
        "failed_count": len(failed),
        "failed": failed,
        "timestamp": timestamp,
    }

    emit({"type": "complete", "result": result})

    return result
