"""既存の全HTMLの <head> 内に AdSense 審査用スクリプトを差し込むワンショットスクリプト。

対象:
- index.html（トップページ）
- about.html / privacy.html / contact.html（静的ページ）
- articles/{category}/*.html（日次・週次）
- articles/*.html（旧構造のIT記事）
- dashboard_*.html（リポジトリ直下のレガシーダッシュボード）

既にマーカー付きで挿入済みの場合は内容を最新化（冪等）。
新規生成分は templates/dashboard.html / generate_index.py / weekly.py のテンプレート側に
同じブロックが入っているため、このスクリプトはデプロイ済み既存分のバックフィル専用。

マーカー:
  <!-- ADSENSE-START --> ... <!-- ADSENSE-END -->
"""
import re
from pathlib import Path

START = "<!-- ADSENSE-START -->"
END = "<!-- ADSENSE-END -->"

ADSENSE_BLOCK = f"""  {START}
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1944739806788973"
     crossorigin="anonymous"></script>
  {END}"""


def upsert_after_head(html):
    """マーカー間を ADSENSE_BLOCK で置換。無ければ <head> の直後に挿入。"""
    pattern = re.compile(
        r"[ \t]*" + re.escape(START) + r".*?" + re.escape(END),
        re.DOTALL,
    )
    if pattern.search(html):
        return pattern.sub(lambda _: ADSENSE_BLOCK, html)

    if "<head>" not in html:
        raise ValueError("アンカー <head> が見つかりません")
    return html.replace("<head>", "<head>\n" + ADSENSE_BLOCK, 1)


def process_file(html_path: Path) -> bool:
    html = html_path.read_text(encoding="utf-8")
    new_html = upsert_after_head(html)
    if new_html == html:
        return False
    html_path.write_text(new_html, encoding="utf-8")
    return True


def main():
    targets = []

    # トップページ + 静的ページ
    for name in ("index.html", "about.html", "privacy.html", "contact.html"):
        p = Path(name)
        if p.exists():
            targets.append(p)

    # 記事・週次（現行構造 articles/{category}/*.html、旧構造 articles/*.html）
    articles_root = Path("articles")
    if articles_root.exists():
        for cat_dir in sorted(articles_root.iterdir()):
            if cat_dir.is_dir():
                targets.extend(sorted(cat_dir.glob("*.html")))
        targets.extend(sorted(articles_root.glob("*.html")))

    # レガシーダッシュボード（リポジトリ直下）
    targets.extend(sorted(Path(".").glob("dashboard_*.html")))

    print(f"対象ファイル数: {len(targets)}")
    updated = 0
    skipped = 0
    for html_file in targets:
        try:
            if process_file(html_file):
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  [NG] エラー: {html_file} - {e}")

    print(f"完了: 更新 {updated} / スキップ {skipped} / 合計 {len(targets)}")


if __name__ == "__main__":
    main()
