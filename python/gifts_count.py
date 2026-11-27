import re
import sys
from collections import defaultdict
from pathlib import Path


# 【メンギフ購入】 @送信者: Sent 個数 ... gift memberships に一致するパターン
PURCHASE_PATTERN = re.compile(
    r"【メンギフ購入】\s*@(?P<sender>[^:\s]+)\s*:\s*Sent\s+(?P<count>\d+)\b.*?\bgift memberships?\b",
    re.IGNORECASE,
)


def aggregate_gifts(input_path: Path) -> dict[str, int]:
    """テキストファイルから送信者ごとのメンギフ購入数を集計する。"""
    totals: dict[str, int] = defaultdict(int)

    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            match = PURCHASE_PATTERN.search(line)
            if match:
                sender = match.group("sender")
                count = int(match.group("count"))
                totals[sender] += count

    # 送信数の多い順にソート（同数は名前の昇順）
    return dict(sorted(totals.items(), key=lambda x: (-x[1], x[0])))


def write_result(output_path: Path, totals: dict[str, int]) -> None:
    """集計結果をテキストファイルに出力する。"""
    total_gifts = sum(totals.values())
    lines = [
        f"対象ファイル: {output_path.name.replace('_gift_result.txt', '.txt')}",
        f"メンギフ合計数: {total_gifts}個",
        "-" * 30,
    ]
    if totals:
        for sender, count in totals.items():
            lines.append(f"@{sender}: {count}個")
    else:
        lines.append("メンギフ購入の記録はありませんでした。")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def gifts_count(input_path: str | Path, output_path: str | Path) -> None:
    in_path = Path(input_path)
    out_path = Path(output_path)

    totals = aggregate_gifts(in_path)
    write_result(out_path, totals)
    print(f"[完了] {in_path} -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    target_path = Path(sys.argv[1])
    output_path = target_path.with_name(f"{target_path.stem}_gift_result.txt")
    gifts_count(target_path, output_path)