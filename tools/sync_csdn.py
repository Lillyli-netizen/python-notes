"""把 CSDN 文章抓成 Markdown，图片下载到本地。

用法：
    python tools/sync_csdn.py <文章URL> <输出md路径>

例：
    python tools/sync_csdn.py https://blog.csdn.net/qq_63283852/article/details/165755775 notes/01_初识与环境准备.md
"""

import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from markdownify import markdownify

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://blog.csdn.net/qq_63283852",
}


def fetch(url: str, tries: int = 3) -> str:
    for i in range(tries):
        resp = requests.get(url, headers=UA, timeout=30)
        # CSDN 偶尔返回 521 反爬页，稍等重试
        if resp.status_code == 200 and "content_views" in resp.text:
            return resp.text
        time.sleep(3 + 3 * i)
    raise SystemExit(f"抓取失败，最后状态码 {resp.status_code}")


def get_content(html: str) -> str:
    start = html.find('id="content_views"')
    if start < 0:
        start = html.find("content_views")
    if start < 0:
        raise SystemExit("没找到正文 content_views，CSDN 页面结构可能变了")
    start = html.rfind("<div", 0, start)
    body = html[start:]
    for end_mark in ('<div id="treeSkill"', '<div id="blogExtensionBox"', "</article>"):
        pos = body.find(end_mark)
        if pos > 0:
            body = body[:pos]
            break
    return body


def download_images(body: str, img_dir: str, md_path: str) -> str:
    os.makedirs(img_dir, exist_ok=True)
    rel_dir = os.path.relpath(img_dir, os.path.dirname(md_path)).replace("\\", "/")
    counter = [0]

    def repl(match):
        whole, tag = match.group(0), match.group(0)
        src = re.search(r'(?:data-src|src)="([^"]+)"', tag)
        if not src:
            return whole
        url = src.group(1)
        if url.startswith("data:"):
            return whole
        url = url.split("?")[0]
        if not re.search(r"\.(png|jpe?g|gif|webp|svg)$", url, re.I):
            return whole
        counter[0] += 1
        name = f"img{counter[0]:02d}" + os.path.splitext(urlparse(url).path)[1].lower()
        try:
            data = requests.get(url, headers={**UA, "Referer": "https://blog.csdn.net/"}, timeout=30).content
            with open(os.path.join(img_dir, name), "wb") as f:
                f.write(data)
        except Exception as exc:  # 单张失败不影响整体
            print(f"图片下载失败 {url}: {exc}")
        return f'<img src="{rel_dir}/{name}" alt="图{counter[0]}">'

    return re.sub(r"<img[^>]*>", repl, body)


def main() -> None:
    url, out = sys.argv[1], sys.argv[2]
    html = fetch(url)
    body = get_content(html)
    body = re.sub(r'<p id="main-toc".*?</p>', "", body, flags=re.S)

    article_id = url.rstrip("/").split("/")[-1]
    img_dir = os.path.join("assets", article_id)
    body = download_images(body, img_dir, out)

    md = markdownify(body, heading_style="ATX", bullets="-")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"写入 {out}：{md.count(chr(10))} 行，图片 {len(os.listdir(img_dir)) if os.path.isdir(img_dir) else 0} 张")


if __name__ == "__main__":
    main()
