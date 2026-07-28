"""鏁版嵁閲囬泦涓婚€昏緫 鈥斺€?澶氭簮鑱氬悎 + 浜ゅ弶鏍￠獙锛堢函 HTTP锛屾棤 akshare 渚濊禆锛?""

import logging
from typing import Any

import requests

from src.data.sources import akshare_source, sina_source, eastmoney_source
from src.data.validator import validate_index_quotes

logger = logging.getLogger("a-share-report")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def collect_all_data(slot: str) -> dict[str, Any]:
    """閲囬泦鎵€鏈夋暟鎹紝鎸夋姤鍛婃椂娈佃皟鏁村唴瀹广€?""
    logger.info(f"寮€濮嬮噰闆嗘暟鎹?(slot={slot})")

    # 鎸囨暟琛屾儏锛堜富婧?+ 澶囩敤婧愶級
    index_data = akshare_source.fetch_index_quotes()
    index_backup = sina_source.fetch_index_quotes()

    # 鏉垮潡琛ㄧ幇
    sector_data = akshare_source.fetch_sector_performance()

    # 娑ㄨ穼姒?    movers_data = akshare_source.fetch_top_movers()

    # 甯傚満姒傚喌
    overview_data = akshare_source.fetch_market_overview()

    # 浜ゅ弶鏍￠獙鎸囨暟
    if index_backup:
        index_data = validate_index_quotes(index_data, index_backup)

    # 鐩樹腑鍙婃敹鐩樻暟鎹細鍖楀悜璧勯噾 & 榫欒檸姒?    north_data: dict = {}
    dragon_data: list = []
    if slot in ("1030", "1130", "1400", "1500"):
        north_data = eastmoney_source.fetch_north_flow()
        if slot in ("1400", "1500"):
            dragon_data = eastmoney_source.fetch_dragon_tiger()

    # 鐩樺墠绠€鎶ョ壒娈婃暟鎹細闅斿缇庤偂
    global_data: dict = {}
    if slot == "0925":
        global_data = _fetch_overnight_global()

    result = {
        "slot": slot,
        "index": index_data,
        "sectors": sector_data,
        "movers": movers_data,
        "overview": overview_data,
        "north_flow": north_data,
        "dragon_tiger": dragon_data,
        "global": global_data,
        "_validation": index_data.pop("_validation", {}),
    }

    logger.info(f"鏁版嵁閲囬泦瀹屾垚 (slot={slot})")
    return result


def _fetch_overnight_global() -> dict[str, Any]:
    """鑾峰彇闅斿鍏ㄧ悆甯傚満鏁版嵁锛堟柊娴?+ 涓滄柟璐㈠瘜锛屾棤闇€ akshare锛?""
    result = {}

    # 绾虫柉杈惧厠鎸囨暟锛堟柊娴級
    try:
        url = "http://hq.sinajs.cn/list=gb_ixic"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = __import__("re").search(r'="(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 2:
                result["us"] = {
                    "index": "绾虫柉杈惧厠",
                    "price": float(vals[1] or 0),
                    "change_pct": float(vals[2] or 0) if len(vals) > 2 else 0,
                }
    except Exception:
        pass

    # 瀵屾椂A50鏈熻揣
    try:
        url = "http://hq.sinajs.cn/list=nf_A50"
        resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
        resp.encoding = "gbk"
        m = __import__("re").search(r'="(.+)"', resp.text)
        if m:
            vals = m.group(1).split(",")
            if len(vals) >= 2:
                result["a50"] = {
                    "price": float(vals[1] or 0),
                    "change_pct": float(vals[2] or 0) if len(vals) > 2 else 0,
                }
    except Exception:
        pass

    return result
