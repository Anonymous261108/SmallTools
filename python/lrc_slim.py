import sys
import re

def clean_lrc(input_path, output_path):
    # タイムスタンプとテキスト部分を分離するための正規表現
    # 例: [58:09.04]テキスト -> マッチ[1]: 58:09.04, マッチ[2]: テキスト
    pattern = re.compile(r'^(\[\d+:\d{2}(?:\.\d+)?\])(.*)$')
    
    cleaned_lines = []
    prev_text = None
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            match = pattern.match(stripped)
            
            if match:
                timestamp, text = match.groups()
                text_stripped = text.strip()
                
                # 条件1: 時間表示だけの行（テキストが空、または空白のみ）は削除
                if not text_stripped:
                    continue
                
                # 条件2: 直前の行とテキストが重複している場合は削除（連続する重複を排除）
                if text_stripped == prev_text:
                    continue
                
                cleaned_lines.append(stripped)
                prev_text = text_stripped
            else:
                # タイムスタンプ形式ではない行はそのまま維持（必要に応じて調整）
                if stripped:
                    cleaned_lines.append(stripped)
                    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned_lines) + '\n')

# 実行例
if __name__ == "__main__":
    
    if len(sys.argv) < 1:
        sys.exit()
        
    inpfnm = sys.argv[1]
    print(f"入力ファイルネーム: {inpfnm}")
    
    outfnm = inpfnm[:-4] + "_lrc.txt"
    print(f"出力ファイルネーム: {outfnm}")
    
    clean_lrc(inpfnm, outfnm)
    print("LRCファイルのクリーニングが完了しました。")
