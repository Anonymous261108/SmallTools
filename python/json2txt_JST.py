import json
import os
import sys
from datetime import datetime, timezone, timedelta

# 日本時間 (JST = UTC+9) のタイムゾーン定義
JST = timezone(timedelta(hours=9))

def extract_youtube_info_jst(json_path, output_path):
    # JSONファイルの読み込み
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 複数動画のリスト形式か、単一動画の辞書形式かを判定
    entries = [data] if isinstance(data, dict) else data
    extracted_records = []

    for item in entries:
        title = item.get('title', '不明なタイトル')
        video_id = item.get('id', '')
        webpage_url = item.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}")
        
        # タイムスタンプの取得
        timestamp = item.get('timestamp') or item.get('release_timestamp')
        
        if timestamp:
            # UNIXタイムスタンプをJST（日本時間）に変換
            dt = datetime.fromtimestamp(timestamp, tz=JST)
            upload_date = dt.strftime('%Y-%m-%d %H:%M:%S JST')
        else:
            # タイムスタンプがない場合は upload_date (YYYYMMDD) から日付のみ取得
            raw_date = item.get('upload_date', '不明な日時')
            if isinstance(raw_date, str) and len(raw_date) == 8 and raw_date.isdigit():
                upload_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]} (時刻不明)"
            else:
                upload_date = raw_date

        description = item.get('description', '概要欄なし')

        record = (
            f"タイトル: {title}\n"
            f"URL: {webpage_url}\n"
            f"投稿日時: {upload_date}\n"
            f"--- 概要欄 ---\n"
            f"{description}\n"
            f"{'='*50}\n"
        )
        extracted_records.append(record)

    # テキストファイルへの書き出し
    with open(output_path, 'w', encoding='utf-8') as out_f:
        out_f.writelines(extracted_records)
    
    print(f"抽出が完了しました。出力ファイル: {output_path}")

# 実行例
if __name__ == "__main__":
    
    if len(sys.argv) < 1:
        sys.exit()

    # 入力するJSONファイル名と出力するTXTファイル名を指定してください
    input_json = sys.argv[1]
    output_txt = input_json[:-4] + "txt"
    
    if os.path.exists(input_json):
        extract_youtube_info_jst(input_json, output_txt)
    else:
        print(f"指定されたファイルが見つかりません: {input_json}")