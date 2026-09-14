#!/usr/bin/env python3
"""Fetch anonymous Bilibili buvid3/buvid4 cookies -> Netscape cookie file for yt-dlp.

Usage: python fetch_bili_cookies.py <out_dir>     # writes <out_dir>/cookies.txt

Workaround for Bilibili HTTP 412: the WAF checks the anonymous buvid cookies even when
Referer + UA are spoofed. Fetch them from the site's own fingerprint SPI endpoint.
Bypasses any system proxy (ProxyHandler({})) so it is not routed through a local proxy.
"""
import sys, json, os, time, secrets, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def spi():
    # GET (not POST, which returns 405). Returns {code, data:{b_3, b_4}}.
    req = urllib.request.Request(
        "https://api.bilibili.com/x/frontend/finger/spi",
        headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.loads(opener.open(req, timeout=20).read().decode())


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    r = spi()
    if r.get("code"):
        raise SystemExit(f"SPI failed: {r}")
    b3 = r["data"]["b_3"]
    b4 = r["data"].get("b_4")
    now = int(time.time())

    def ck(d, p, sec, e, n, v):
        return "\t".join([d, "TRUE" if d.startswith(".") else "FALSE", p,
                           "TRUE" if sec else "FALSE", str(e), n, v])

    lines = ["# Netscape HTTP Cookie File",
             ck(".bilibili.com", "/", True, now + 31536000, "buvid3", b3)]
    if b4:
        lines.append(ck(".bilibili.com", "/", True, now + 31536000, "buvid4", b4))
    lines.append(ck(".bilibili.com", "/", True, now + 31536000, "b_nut", str(now)))
    lines.append(ck(".bilibili.com", "/", True, now + 31536000, "b_lsid",
                    "".join(secrets.choice("0123456789abcdefxz") for _ in range(32))))
    path = os.path.join(out_dir, "cookies.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote", path)


if __name__ == "__main__":
    main()
