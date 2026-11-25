
import json
import os
import sys


def usec_to_hms(usec):
  """マイクロ秒から安全に HH:MM:SS 形式のタイムスタンプを生成する

  異常に大きな数値（例: バグによる誤爆）が入った場合は空文字を返す
  """
  try:
    total_sec = int(usec) // 1_000_000
    # 万が一、配信時間を大きく超えるような異常値（例: 100時間以上など）なら無視する
    if total_sec < 0 or total_sec > 359999:  # 100時間上限
      return ""
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    if hours > 0:
      return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
      return f"{minutes:02d}:{seconds:02d}"  # 分は2桁表示で綺麗に
  except (TypeError, ValueError):
    return ""


def parse_runs(runs):
  """message.runs の配列からテキストとカスタム絵文字のショートカットを結合する"""
  if not isinstance(runs, list):
    return ""
  text_parts = []
  for r in runs:
    if "text" in r:
      text_parts.append(r["text"])
    elif "emoji" in r:
      shortcuts = r["emoji"].get("shortcuts", [])
      if shortcuts:
        text_parts.append(shortcuts[0])
      else:
        label = (
            r["emoji"]
            .get("image", {})
            .get("accessibility", {})
            .get("accessibilityData", {})
            .get("label", "絵文字")
        )
        text_parts.append(f"[{label}]")
  return "".join(text_parts)


def parse_live_chat(json_path, output_path):
  if not os.path.exists(json_path):
    print(f"エラー: ファイル '{json_path}' が見つかりません。")
    return

  # ★ milestone をカウント項目に追加
  counts = {
      "text": 0,
      "superchat": 0,
      "sticker": 0,
      "gift_buy": 0,
      "gift_get": 0,
      "milestone": 0,
  }

  print(f"解析中: {json_path}")
  with (
      open(json_path, "r", encoding="utf-8") as f_in,
      open(output_path, "w", encoding="utf-8") as f_out,
  ):
    f_out.write(f"=== ライブチャット抽出ログ: {os.path.basename(json_path)} ===\n\n")

    for line in f_in:
      line = line.strip()
      if not line or line == "{":
        continue
      try:
        data = json.loads(line)
      except json.JSONDecodeError:
        continue

      actions = data.get("replayChatItemAction", {}).get("actions", [])
      for act in actions:
        add_action = act.get("addChatItemAction", {})
        item = add_action.get("item", {})
        if not item:
          continue

        renderer = None
        event_type = None

        if "liveChatTextMessageRenderer" in item:
          renderer = item["liveChatTextMessageRenderer"]
          event_type = "text"
        elif "liveChatPaidMessageRenderer" in item:
          renderer = item["liveChatPaidMessageRenderer"]
          event_type = "superchat"
        elif "liveChatPaidStickerRenderer" in item:
          renderer = item["liveChatPaidStickerRenderer"]
          event_type = "sticker"
        elif "liveChatSponsorshipsGiftPurchaseAnnouncementRenderer" in item:
          renderer = item["liveChatSponsorshipsGiftPurchaseAnnouncementRenderer"]
          event_type = "gift_buy"
        elif "liveChatSponsorshipsGiftRedemptionAnnouncementRenderer" in item:
          renderer = item["liveChatSponsorshipsGiftRedemptionAnnouncementRenderer"]
          event_type = "gift_get"
        # ★ メンバーシップ関連の判定を追加
        elif "liveChatMembershipItemRenderer" in item:
          temp_renderer = item["liveChatMembershipItemRenderer"]
          # 「コメント付きマイルストーン」のみを対象にする（message と headerPrimaryText の両方があるもの）
          if "message" in temp_renderer and "headerPrimaryText" in temp_renderer:
            renderer = temp_renderer
            event_type = "milestone"

        if not renderer:
          continue

        # タイムスタンプの取得優先順位：
        # 1. timestampText (一番確実)
        # 2. videoOffsetTimeMsec (ミリ秒オフセット)
        # 3. timestampUsec (マイクロ秒・ただし上記でダメな場合のみ慎重に)
        ts = ""
        ts_obj = renderer.get("timestampText")
        if ts_obj and isinstance(ts_obj, dict):
          ts = ts_obj.get("simpleText", "")

        if not ts:
          # videoOffsetTimeMsec があれば優先して使う（ミリ秒）
          msec = renderer.get("videoOffsetTimeMsec") or item.get(
              "videoOffsetTimeMsec"
          )
          if msec:
            try:
              total_sec = int(msec) // 1000
              h = total_sec // 3600
              m = (total_sec % 3600) // 60
              s = total_sec % 60
              ts = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            except (TypeError, ValueError):
              pass

        if not ts:
          # 最終手段として timestampUsec を使うが、異常値ガードを通す
          usec = renderer.get("timestampUsec")
          if usec:
            ts = usec_to_hms(usec)

        if not ts:
          ts = "00:00"

        # 投稿者名の取得
        author = "不明"
        if "authorName" in renderer:
          author = renderer["authorName"].get("simpleText", "不明")
        elif event_type == "gift_buy":
          header = renderer.get("header", {}).get(
              "liveChatSponsorshipsHeaderRenderer", {}
          )
          author = header.get("authorName", {}).get("simpleText", "不明")

        # 出力の書き込み
        if event_type == "text":
          msg = parse_runs(renderer.get("message", {}).get("runs", []))
          f_out.write(f"[{ts}] {author}: {msg}\n")
          counts["text"] += 1

        elif event_type == "superchat":
          amount = renderer.get("purchaseAmountText", {}).get(
              "simpleText", "金額不明"
          )
          msg = parse_runs(renderer.get("message", {}).get("runs", []))
          line_str = f"[{ts}] 【スパチャ ({amount})】 {author}:"
          if msg:
            line_str += f" {msg}"
          f_out.write(line_str + "\n")
          counts["superchat"] += 1

        elif event_type == "sticker":
          amount = renderer.get("purchaseAmountText", {}).get(
              "simpleText", "金額不明"
          )
          sticker_label = (
              renderer.get("sticker", {})
              .get("accessibility", {})
              .get("accessibilityData", {})
              .get("label", "ステッカー")
          )
          f_out.write(
              f"[{ts}] 【スーパーステッカー ({amount})】 {author}:"
              f" [{sticker_label}]\n"
          )
          counts["sticker"] += 1

        elif event_type == "gift_buy":
          header = renderer.get("header", {}).get(
              "liveChatSponsorshipsHeaderRenderer", {}
          )
          primary_text = parse_runs(
              header.get("primaryText", {}).get("runs", [])
          )
          f_out.write(f"[{ts}] 【メンギフ購入】 {author}: {primary_text}\n")
          counts["gift_buy"] += 1

        elif event_type == "gift_get":
          msg = parse_runs(renderer.get("message", {}).get("runs", []))
          f_out.write(f"[{ts}] 【メンギフ受取】 {author}: {msg}\n")
          counts["gift_get"] += 1

        # ★ コメント付きマイルストーンの書き込み処理を追加
        elif event_type == "milestone":
          milestone_period = parse_runs(
              renderer.get("headerPrimaryText", {}).get("runs", [])
          )
          msg = parse_runs(renderer.get("message", {}).get("runs", []))
          f_out.write(
              f"[{ts}] 【メンバー継続 ({milestone_period})】 {author}: {msg}\n"
          )
          counts["milestone"] += 1

  print("\n=== 解析完了 ===")
  print(f"  通常チャット: {counts['text']} 件")
  print(f"  スパチャ: {counts['superchat']} 件")
  print(f"  スーパーステッカー: {counts['sticker']} 件")
  print(f"  メンギフ購入: {counts['gift_buy']} 件")
  print(f"  メンギフ受取: {counts['gift_get']} 件")
  print(f"  メンバー継続（コメント付）: {counts['milestone']} 件")
  print(f"📁 保存先ファイル: {output_path}")


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print(
        "使い方: python parse_live_chat_clean.py <ファイル名.live_chat.json>"
    )
    sys.exit(1)

  target_json = sys.argv[1]
  output_txt = os.path.splitext(target_json)[0] + "_parsed_chat.txt"
  parse_live_chat(target_json, output_txt)
