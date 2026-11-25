from datetime import datetime
import json
import os
import sys


def parse_comments_json(json_path):
    """yt-dlpで出力されたコメントを含むinfo.jsonを解析してテキストに出力する（投稿日時対応）"""
    if not os.path.exists(json_path):
        print(f"ファイルが見つかりません: {json_path}")
        return

    output_path = os.path.splitext(json_path)[0] + "_parsed_comments.txt"
    print(f"  [処理中] {os.path.basename(json_path)} ...")

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("JSONの読み込みに失敗しました。")
            return

    comments = data.get("comments", [])
    if not comments:
        print("コメントデータが見つかりませんでした。")
        return

    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write(f"=== コメント抽出ログ: {data.get('title', '不明')} ===\n")
        f_out.write(f"チャンネル: {data.get('uploader', '不明')}\n\n")

        for c in comments:
            author = c.get("author", "不明")
            text = c.get("text", "").replace("\n", " ")  # 改行を置換して1行に
            likes = c.get("like_count", 0)

            # 投稿日時の取得と変換
            # yt-dlpのコメントには 'timestamp' (エポック秒) または 'text_date' (「2日前」などの相対表現) が入っています
            timestamp = c.get("timestamp")
            if timestamp:
                try:
                    #dt_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    #時間は全部09:00:00になるのでなし                
                    dt_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                except (TypeError, ValueError):
                    dt_str = c.get("text_date", "日時不明")
            else:
                dt_str = c.get("text_date", "日時不明")

            f_out.write(f"[{dt_str}] [{author}] (👍 {likes})\n{text}\n")
            f_out.write("-" * 40 + "\n")

    print(f"  -> 完了: {len(comments)} 件のコメントを保存しました: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_json = sys.argv[1]
        parse_comments_json(target_json)
    else:
        import glob
        files = glob.glob("*.info.json")
        if not files:
            print("*.info.json が見つかりません。")
        else:
            for f in files:
                parse_comments_json(f)