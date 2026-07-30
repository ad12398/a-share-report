"""部署脚本 —— 生成报告并推送到 GitHub Pages（服务器端运行）"""
import base64
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows Server SSL 证书兼容
ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = os.environ.get("GH_TOKEN", "")
REPO = "ad12398/a-share-report"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
}

# 北京时间
BEIJING_TZ = timezone(timedelta(hours=8))
PROJECT_ROOT = Path(__file__).parent
REPORTS_DIR = PROJECT_ROOT / "reports"


def get_sha(path, branch="gh-pages"):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={branch}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def put_file(path, content_str, msg, branch="gh-pages"):
    sha = get_sha(path, branch)
    payload = {
        "message": msg,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  OK: {path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  FAIL: {path} -> {e.read().decode()}")
        return False


def deploy():
    """生成一份报告并推送"""
    if not TOKEN:
        print("错误: 请设置 GH_TOKEN 环境变量")
        print("  setx GH_TOKEN \"你的GitHub Token\"")
        sys.exit(1)

    # 获取 slot
    slot = sys.argv[1] if len(sys.argv) > 1 else None
    if not slot:
        now = datetime.now(BEIJING_TZ)
        hour = now.hour
        minute = now.minute
        if hour < 9 or (hour == 9 and minute < 25):
            slot = "0925"
        elif hour < 10 or (hour == 10 and minute < 30):
            slot = "1030"
        elif hour < 11 or (hour == 11 and minute < 30):
            slot = "1130"
        elif hour < 14:
            slot = "1400"
        elif hour < 15:
            slot = "1500"
        else:
            print("当前不在交易时段")
            sys.exit(0)

    print(f"[{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}] 开始生成报告 slot={slot}")

    # 1. 运行主程序生成报告
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.main import run
    result = run(slot)
    if not result:
        print("报告生成失败（可能是非交易日）")
        sys.exit(0)

    print(f"报告已生成: {result}")

    # 2. 推送报告文件到 gh-pages
    print("推送到 GitHub Pages...")
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    files_to_push = [
        (f"reports/{today}/{slot}.html", f"report: {today} {slot}"),
        (f"reports/{today}/{slot}.docx", f"docx: {today} {slot}"),
        (f"reports/index.html", f"index: {today} {slot}"),
        (f"reports/archives.html", f"archives: {today} {slot}"),
    ]

    # 推送搜索索引（如果存在）
    index_json = PROJECT_ROOT / "data" / "index.json"
    if index_json.exists():
        files_to_push.append(("data/index.json", f"search index: {today} {slot}"))

    for path, msg in files_to_push:
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            print(f"  跳过(文件不存在): {path}")
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        put_file(path, content, msg)

    print("部署完成!")


if __name__ == "__main__":
    deploy()
