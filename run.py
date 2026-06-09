"""CLI entry point — delegates to downloader module."""

import os

from downloader import process_excel

os.makedirs("downloads", exist_ok=True)
os.makedirs("output", exist_ok=True)


def on_progress(event):
    event_type = event.get("type")

    if event_type == "item_start":
        print(f"\n[{event['current']}/{event['total']}] 正在处理:")
        print(event["filename"])

    elif event_type == "item_done":
        if event.get("success"):
            print("✓ 成功")
        else:
            print(f"✗ 失败 — {event.get('reason', '')}")

    elif event_type == "zip_start":
        print("\n正在生成 ZIP...")

    elif event_type == "complete":
        result = event["result"]
        print("\n====================")
        print("ZIP生成成功")
        print(result["zip_path"])
        print("====================")
        if result["failed_path"]:
            print("\n失败记录:")
            print(result["failed_path"])
        print("\n全部完成")


if __name__ == "__main__":
    process_excel("input.xlsx", "output", on_progress=on_progress)
