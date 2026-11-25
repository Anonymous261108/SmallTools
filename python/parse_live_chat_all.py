import glob
import json
import os
import sys


def usec_to_hms(usec):
    """マイクロ秒から安全に HH:MM:SS 形式のタイムスタンプを生成する"""
    try:
        total_sec = int(usec) // 1_000_000
        if total_sec < 0 or total_sec > 359999:
            return ""
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        seconds = total_sec % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
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


def parse_single_file(json_path):
    """1つのJSONファイルを解析してテキストファイルに出力する"""
    output_path = os.path.splitext(json_path)[0] + "_parsed_chat.txt"
    counts = {
        "text": 0,
        "superchat": 0,
        "sticker": 0,
        "gift_buy": 0,
        "gift_get": 0,
        "membership": 0,
    }

    print(f"  [処理中] {os.path.basename(json_path)} ...")

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
                elif "liveChatMembershipItemRenderer" in item:
                    renderer = item["liveChatMembershipItemRenderer"]
                    event_type = "membership"

                if not renderer:
                    continue

                # タイムスタンプ取得
                ts = ""
                ts_obj = renderer.get("timestampText")
                if ts_obj and isinstance(ts_obj, dict):
                    ts = ts_obj.get("simpleText", "")

                if not ts:
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
                    usec = renderer.get("timestampUsec")
                    if usec:
                        ts = usec_to_hms(usec)

                if not ts:
                    ts = "00:00"

                # 投稿者名取得
                author = "不明"
                if "authorName" in renderer:
                    author = renderer["authorName"].get("simpleText", "不明")
                elif event_type in ["gift_buy", "membership"]:
                    header = renderer.get("header", {}).get(
                        "liveChatSponsorshipsHeaderRenderer", {}
                    )
                    author = header.get("authorName", {}).get("simpleText", "不明")

                # ファイルへ書き出し
                if event_type == "text":
                    msg = parse_runs(renderer.get("message", {}).get("runs", []))
                    f_out.write(f"[{ts}] {author}: {msg}\n")
                    counts["text"] += 1
                elif event_type == "superchat":
                    amount = renderer.get("purchaseAmountText", {}).get(
                        "simpleText", "金額不明"
                    )
                    msg = parse_runs(renderer.get("message", {}).get("runs", []))
                    line_str = f"[{ts}] 【スパチャ ({amount})】 {author}"
                    if msg:
                        line_str += f": {msg}"
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
                        f"[{ts}] 【スーパーステッカー ({amount})】 {author}: [{sticker_label}]\n"
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
                elif event_type == "membership":
                    header = renderer.get("header", {}).get(
                        "liveChatSponsorshipsHeaderRenderer", {}
                    )
                    primary_text = parse_runs(
                        header.get("primaryText", {}).get("runs", [])
                    )
                    msg = parse_runs(renderer.get("message", {}).get("runs", []))
                    
                    line_str = f"[{ts}] 【メンバーシップ】 {author}"
                    if primary_text:
                        line_str += f" ({primary_text})"
                    if msg:
                        line_str += f": {msg}"
                    f_out.write(line_str + "\n")
                    counts["membership"] += 1

    print(
        f"    -> 完了: 通常 {counts['text']}件 / スパチャ {counts['superchat']}件"
        f" / メンギフ {counts['gift_buy']+counts['gift_get']}件"
        f" / メンバーシップ {counts['membership']}件"
    )


def batch_process(target_dir):
    search_pattern = os.path.join(target_dir, "*.live_chat.json")
    files = glob.glob(search_pattern)

    if not files:
        print(f"指定された場所（{target_dir}）に .live_chat.json が見つかりません。")
        return

    print(f"合計 {len(files)} 件のライブチャットファイルが見つかりました。\n")

    for file_path in files:
        parse_single_file(file_path)

    print("\n=== すべてのファイルの変換が完了しました！ ===")


if __name__ == "__main__":
    target_directory = sys.argv[1] if len(sys.argv) > 1 else "."
    batch_process(target_directory)