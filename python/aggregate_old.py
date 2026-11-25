#新規メンバー加入　書き込み数にカウント
#コメントなしのマイルストーン　書き込み数にカウント
#コメントなしのスパチャ　書き込み数にカウント

from collections import defaultdict
import re
import sys

# コマンドライン引数が指定されているかチェック
if len(sys.argv) < 2:
  print("使い方: python script.py <チャットデータのファイル名>")
  print("例: python script.py chat.txt")
  sys.exit(1)

# 入力ファイル名を sys.argv[1] から取得
input_filename = sys.argv[1]
# 出力ファイル名は入力ファイル名の後ろに "_result.txt" を付与
output_filename = input_filename[:-4] + "_result.txt"

# ユーザーごとのデータを保持する辞書
user_stats = defaultdict(lambda: {"comments": 0, "superchat": 0})

try:
  # ファイルからチャットデータを読み込む
  with open(input_filename, "r", encoding="utf-8") as f:
    chat_data = f.read()

  # 行ごとにパースして集計
  for line in chat_data.strip().split("\n"):
    # スパチャ行の判定 ([時間] 【スパチャ (¥金額)】 @ユーザー名)
    sc_match = re.search(r"【スパチャ\s*\(¥(\d+)\)】\s*@(\S+)", line)
    if sc_match:
      amount = int(sc_match.group(1))
      user = sc_match.group(2)
      user_stats[user]["superchat"] += amount
      #コメントなしのスパチャ　書き込み数にカウント
      user_stats[user]["comments"] += 1      
      continue

    # メンバー継続行の判定 ([時間] 【メンバー継続 ...】 @ユーザー名: メッセージ)
    member_match = re.search(r"【メンバー継続[^】]*】\s*@([^:]+):\s*(.*)", line)
    if member_match:
      user = member_match.group(1).strip()
      user_stats[user]["comments"] += 1
      continue

    # 新規メンバー行の判定 ([時間] 【新規メンバー ...】 @ユーザー名: メッセージ)
    new_member_match = re.search(
        r"【新規メンバー[^】]*】\s*@([^:]+):\s*(.*)", line
    )
    if new_member_match:
      user = new_member_match.group(1).strip()
      user_stats[user]["comments"] += 1
      continue

    # 通常コメント行の判定 ([時間] @ユーザー名: メッセージ)
    comment_match = re.search(r"\[.*?\]\s*@([^:]+):\s*(.*)", line)
    if comment_match:
      user = comment_match.group(1).strip()
      user_stats[user]["comments"] += 1

  # 総合ランキングのソート
  # 優先度1: スパチャ金額（降順）、優先度2: 書き込み回数（降順）
  sorted_users = sorted(
      user_stats.items(),
      key=lambda x: (x[1]["superchat"], x[1]["comments"]),
      reverse=True,
  )

  # 出力用のテキストデータを作成
  output_lines = []
  output_lines.append(
      f"{'ユーザー名':<16} | {'書き込み回数':<10} | {'スパチャ合計':<10}"
  )
  output_lines.append("-" * 46)
  for user, stats in sorted_users:
    output_lines.append(
        f"@{user:<15} | {stats['comments']:>6}回      |"
        f" ¥{stats['superchat']:>7,}"
    )

  result_text = "\n".join(output_lines)

  # 結果を別ファイルに書き込む
  with open(output_filename, "w", encoding="utf-8") as f:
    f.write(result_text)

  print(f"集計が完了しました。結果を '{output_filename}' に保存しました。")
  print("\n--- 集計結果プレビュー ---\n" + result_text)

except FileNotFoundError:
  print(
      f"エラー: 入力ファイル '{input_filename}' が見つかりません。"
      "ファイル名やパスに誤りがないか確認してください。"
  )
