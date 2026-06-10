import os
import re
import zipfile
import time
from datetime import datetime
from typing import Callable, Optional

import pandas as pd
import yt_dlp
import gdown


# ======================
# 工具
# ======================
def clean_text(text: str) -> str:
    return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", str(text))


def build_filename(row) -> str:
    return f"{row['code']} {row['version']} {row['video']} {row['language']} {row['size']} {row['game']}"


ProgressCallback = Callable[[dict], None]


# ======================
# 🔥 gdown防卡死版本
# ======================
def safe_gdown(url, output_file, retry=3):
    for i in range(retry):
        try:
            gdown.download(url, output_file, quiet=False)

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return True

        except Exception as e:
            print(f"[gdown retry {i}] {e}")

        time.sleep(2)

    return False


# ======================
# yt-dlp防卡死版本
# ======================
def safe_ytdlp(url, downloads_dir, filename):

    try:
        ydl_opts = {
            "outtmpl": f"{downloads_dir}/{filename}.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,   # 🔥 防卡死关键
        }

        before = set(os.listdir(downloads_dir))

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        after = set(os.listdir(downloads_dir))
        new_files = list(after - before)

        if not new_files:
            return None

        return os.path.join(downloads_dir, new_files[0])

    except Exception as e:
        print("yt-dlp error:", e)
        return None


# ======================
# 主函数
# ======================
def process_excel(
    excel_path: str,
    output_dir: str,
    on_progress: Optional[ProgressCallback] = None,
) -> dict:

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

    # 清空旧文件
    for f in os.listdir(downloads_dir):
        try:
            os.remove(os.path.join(downloads_dir, f))
        except:
            pass

    # ======================
    # 主循环
    # ======================
    for index, row in df.iterrows():

        filename = build_filename(row)
        url = str(row["url"]).strip()

        emit({
            "type": "item_start",
            "current": index + 1,
            "total": total,
            "filename": filename,
            "url": url,
        })

        file_path = None

        try:
            # ======================
            # TikTok / yt-dlp
            # ======================
            if "tiktok" in url.lower():
                file_path = safe_ytdlp(url, downloads_dir, filename)

                if not file_path:
                    raise Exception("yt-dlp下载失败或超时")

            # ======================
            # Google Drive
            # ======================
            elif "drive.google" in url.lower():

                file_path = os.path.join(downloads_dir, f"{filename}.mp4")

                success = safe_gdown(url, file_path)

                if not success:
                    raise Exception("Google Drive下载失败或超时")

                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("文件为空")

            else:
                raise Exception("不支持的链接类型")

            downloaded_files.append(file_path)

            emit({
                "type": "item_done",
                "current": index + 1,
                "total": total,
                "filename": filename,
                "success": True,
            })

        except Exception as e:

            failed.append({
                "filename": filename,
                "url": url,
                "reason": clean_text(str(e)),
            })

            emit({
                "type": "item_done",
                "current": index + 1,
                "total": total,
                "filename": filename,
                "success": False,
                "reason": str(e),
            })

    # ======================
    # ZIP生成（绝对不会卡死）
    # ======================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(output_dir, f"videos_{timestamp}.zip")

    emit({"type": "zip_start", "total": len(downloaded_files)})

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for f in downloaded_files:
            if f and os.path.exists(f):
                zipf.write(f, os.path.basename(f))

    # ======================
    # failed report
    # ======================
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