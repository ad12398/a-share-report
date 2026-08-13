"""部署脚本 —— 生成报告并推送到 GitHub Pages（服务器端运行）"""
import base64
import json
import os
import ssl
import sys
import urllib.parse
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
    encoded = urllib.parse.quote(path, safe="/")
    url = f"https://api.github.com/repos/{REPO}/contents/{encoded}?ref={branch}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  WARN: get_sha {path} HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  WARN: get_sha {path} 失败: {e}")
        return None


def put_file_binary(path, content_b64, msg, branch="gh-pages"):
    """推送二进制文件（content_b64 已 base64 编码）"""
    sha = get_sha(path, branch)
    encoded = urllib.parse.quote(path, safe="/")
    payload = {
        "message": msg,
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/{encoded}"
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  OK: {path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  FAIL: {path} -> HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  FAIL: {path} -> {e}")
        return False


def put_file(path, content_str, msg, branch="gh-pages"):
    sha = get_sha(path, branch)
    encoded = urllib.parse.quote(path, safe="/")
    payload = {
        "message": msg,
        "content": base64.b64encode(content_str.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/contents/{encoded}"
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"  OK: {path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  FAIL: {path} -> HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  FAIL: {path} -> {e}")
        return False


def deploy():
    """生成一份报告并推送"""
    if not TOKEN:
        print("错误: 请设置 GH_TOKEN 环境变量")
        print("  setx GH_TOKEN \"你的GitHub Token\"")
        sys.exit(1)

    # 获取 slot：手动参数优先，否则复用 calendar 的精确时段窗口
    # （错时手动触发不再生成错误时段的报告）
    slot = sys.argv[1] if len(sys.argv) > 1 else None
    if not slot:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.data.calendar import get_current_slot
        slot = get_current_slot()
        if not slot:
            print("当前不在报告时段内")
            sys.exit(0)

    print(f"[{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}] 开始生成报告 slot={slot}")

    # 1. 运行主程序生成报告
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.main import run
    result = run(slot)
    if not result:
        print("报告生成失败（可能是非交易日）")
        sys.exit(1)

    print(f"报告已生成: {result}")

    # 2. 推送报告文件到 gh-pages
    print("推送到 GitHub Pages...")
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    # 找当前时段对应的 docx 文件（文件名含中文时段，如"09时25分"）
    slot_hour = slot[:2]
    slot_min = slot[2:]
    time_key = f"{slot_hour}时{slot_min}分"
    docx_files = sorted(Path(f"reports/{today}").glob(f"*{time_key}*.docx"))
    docx_path = f"reports/{today}/{docx_files[0].name}" if docx_files else f"reports/{today}/{slot}.docx"

    files_to_push = [
        (f"reports/{today}/{slot}.html", f"report: {today} {slot}"),
        (docx_path, f"docx: {today} {slot}"),
        (f"reports/index.html", f"index: {today} {slot}"),
        (f"reports/archives.html", f"archives: {today} {slot}"),
        (f"assets/css/dashboard.css", f"css: {today} {slot}"),
    ]

    # 生成并推送统计面板
    try:
        from src.web.renderer import render_stats_page, save_stats_html
        stats_html = render_stats_page()
        stats_path = save_stats_html(stats_html)
        files_to_push.append((f"reports/stats.html", f"stats: {today} {slot}"))
        print(f"统计面板已生成")
    except Exception as e:
        print(f"统计面板生成失败: {e}")

    # 推送搜索索引（如果存在）
    index_json = PROJECT_ROOT / "data" / "index.json"
    if index_json.exists():
        files_to_push.append(("data/index.json", f"search index: {today} {slot}"))

    failed_count = 0
    for path, msg in files_to_push:
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            print(f"  跳过(文件不存在): {path}")
            continue
        # .docx 是二进制文件，用 base64 编码
        try:
            if path.endswith(".docx"):
                with open(full_path, "rb") as f:
                    content = base64.b64encode(f.read()).decode("ascii")
                ok = put_file_binary(path, content, msg)
            else:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                ok = put_file(path, content, msg)
        except Exception as e:
            print(f"  FAIL: {path} -> 读取文件异常: {e}")
            ok = False
        if not ok:
            failed_count += 1

    if failed_count:
        print(f"部署完成，但 {failed_count} 个文件推送失败（gh-pages 可能不完整）")
        sys.exit(1)
    print("部署完成!")


if __name__ == "__main__":
    deploy()
