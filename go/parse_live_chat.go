package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// usecToHms マイクロ秒から HH:MM:SS 形式のタイムスタンプを生成する
func usecToHms(usec interface{}) string {
	var usecVal int64
	switch v := usec.(type) {
	case float64:
		usecVal = int64(v)
	case int64:
		usecVal = v
	case int:
		usecVal = int64(v)
	default:
		return ""
	}

	totalSec := usecVal / 1_000_000
	if totalSec < 0 || totalSec > 359999 { // 100時間上限
		return ""
	}

	hours := totalSec / 3600
	minutes := (totalSec % 3600) / 60
	seconds := totalSec % 60

	if hours > 0 {
		return fmt.Sprintf("%d:%02d:%02d", hours, minutes, seconds)
	}
	return fmt.Sprintf("%02d:%02d", minutes, seconds)
}

// parseRuns message.runs の配列からテキストとカスタム絵文字のショートカットを結合する
func parseRuns(runs interface{}) string {
	runsList, ok := runs.([]interface{})
	if !ok {
		return ""
	}

	var textParts []string
	for _, r := range runsList {
		run, ok := r.(map[string]interface{})
		if !ok {
			continue
		}

		if text, ok := run["text"].(string); ok {
			textParts = append(textParts, text)
		} else if emoji, ok := run["emoji"].(map[string]interface{}); ok {
			shortcuts, ok := emoji["shortcuts"].([]interface{})
			if ok && len(shortcuts) > 0 {
				if s, ok := shortcuts[0].(string); ok {
					textParts = append(textParts, s)
				}
			} else {
				label := "絵文字"
				// 深い階層の map を辿る
				if img, ok := emoji["image"].(map[string]interface{}); ok {
					if acc, ok := img["accessibility"].(map[string]interface{}); ok {
						if accData, ok := acc["accessibilityData"].(map[string]interface{}); ok {
							if l, ok := accData["label"].(string); ok {
								label = l
							}
						}
					}
				}
				textParts = append(textParts, fmt.Sprintf("[%s]", label))
			}
		}
	}
	return strings.Join(textParts, "")
}

// getSimpleText map から simpleText フィールドを安全に抽出する
func getSimpleText(m interface{}) string {
	if obj, ok := m.(map[string]interface{}); ok {
		if txt, ok := obj["simpleText"].(string); ok {
			return txt
		}
	}
	return ""
}

func parseLiveChat(jsonPath, outputPath string) {
	fIn, err := os.Open(jsonPath)
	if err != nil {
		fmt.Printf("エラー: ファイル '%s' が見つかりません。\n", jsonPath)
		return
	}
	defer fIn.Close()

	fOut, err := os.Create(outputPath)
	if err != nil {
		fmt.Printf("エラー: 出力ファイルの作成に失敗しました: %v\n", err)
		return
	}
	defer fOut.Close()

	writer := bufio.NewWriter(fOut)
	defer writer.Flush()

	counts := map[string]int{
		"text":      0,
		"superchat": 0,
		"sticker":   0,
		"gift_buy":  0,
		"gift_get":  0,
		"milestone": 0,
	}

	fmt.Printf("解析中: %s\n", jsonPath)
	writer.WriteString(fmt.Sprintf("=== ライブチャット抽出ログ: %s ===\n\n", filepath.Base(jsonPath)))

	scanner := bufio.NewScanner(fIn)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || line == "{" {
			continue
		}

		var data map[string]interface{}
		if err := json.Unmarshal([]byte(line), &data); err != nil {
			continue
		}

		replayAction, ok := data["replayChatItemAction"].(map[string]interface{})
		if !ok {
			continue
		}
		actions, ok := replayAction["actions"].([]interface{})
		if !ok {
			continue
		}

		for _, actRaw := range actions {
			act, ok := actRaw.(map[string]interface{})
			if !ok {
				continue
			}
			addChatItemAction, ok := act["addChatItemAction"].(map[string]interface{})
			if !ok {
				continue
			}
			item, ok := addChatItemAction["item"].(map[string]interface{})
			if !ok {
				continue
			}

			var renderer map[string]interface{}
			var eventType string

			if r, ok := item["liveChatTextMessageRenderer"].(map[string]interface{}); ok {
				renderer = r
				eventType = "text"
			} else if r, ok := item["liveChatPaidMessageRenderer"].(map[string]interface{}); ok {
				renderer = r
				eventType = "superchat"
			} else if r, ok := item["liveChatPaidStickerRenderer"].(map[string]interface{}); ok {
				renderer = r
				eventType = "sticker"
			} else if r, ok := item["liveChatSponsorshipsGiftPurchaseAnnouncementRenderer"].(map[string]interface{}); ok {
				renderer = r
				eventType = "gift_buy"
			} else if r, ok := item["liveChatSponsorshipsGiftRedemptionAnnouncementRenderer"].(map[string]interface{}); ok {
				renderer = r
				eventType = "gift_get"
			} else if r, ok := item["liveChatMembershipItemRenderer"].(map[string]interface{}); ok {
				if _, hasMsg := r["message"]; hasMsg {
					if _, hasHeader := r["headerPrimaryText"]; hasHeader {
						renderer = r
						eventType = "milestone"
					}
				}
			}

			if renderer == nil {
				continue
			}

			// タイムスタンプの取得
			ts := ""
			ts = getSimpleText(renderer["timestampText"])

			if ts == "" {
				msecRaw := renderer["videoOffsetTimeMsec"]
				if msecRaw == nil {
					msecRaw = item["videoOffsetTimeMsec"]
				}
				if msecRaw != nil {
					var msec int64
					switch v := msecRaw.(type) {
					case float64:
						msec = int64(v)
					case int64:
						msec = v
					case int:
						msec = int64(v)
					}
					totalSec := msec / 1000
					h := totalSec / 3600
					m := (totalSec % 3600) / 60
					s := totalSec % 60
					if h > 0 {
						ts = fmt.Sprintf("%d:%02d:%02d", h, m, s)
					} else {
						ts = fmt.Sprintf("%02d:%02d", m, s)
					}
				}
			}

			if ts == "" {
				ts = usecToHms(renderer["timestampUsec"])
			}

			if ts == "" {
				ts = "00:00"
			}

			// 投稿者名の取得
			author := "不明"
			if authorObj, ok := renderer["authorName"]; ok {
				author = getSimpleText(authorObj)
			} else if eventType == "gift_buy" {
				if header, ok := renderer["header"].(map[string]interface{}); ok {
					if hRenderer, ok := header["liveChatSponsorshipsHeaderRenderer"].(map[string]interface{}); ok {
						author = getSimpleText(hRenderer["authorName"])
					}
				}
			}
			if author == "" {
				author = "不明"
			}

			// 出力の書き込み
			switch eventType {
			case "text":
				msg := parseRuns(getNestedMap(renderer, "message", "runs"))
				writer.WriteString(fmt.Sprintf("[%s] %s: %s\n", ts, author, msg))
				counts["text"]++
			case "superchat":
				amount := getSimpleText(renderer["purchaseAmountText"])
				if amount == "" {
					amount = "金額不明"
				}
				msg := parseRuns(getNestedMap(renderer, "message", "runs"))
				lineStr := fmt.Sprintf("[%s] 【スパチャ (%s)】 %s: ", ts, amount, author)
				if msg != "" {
					lineStr += fmt.Sprintf("%s", msg)
				}
				writer.WriteString(lineStr + "\n")
				counts["superchat"]++
			case "sticker":
				amount := getSimpleText(renderer["purchaseAmountText"])
				if amount == "" {
					amount = "金額不明"
				}
				stickerLabel := "ステッカー"
				if sticker, ok := renderer["sticker"].(map[string]interface{}); ok {
					if acc, ok := sticker["accessibility"].(map[string]interface{}); ok {
						if accData, ok := acc["accessibilityData"].(map[string]interface{}); ok {
							if l, ok := accData["label"].(string); ok {
								stickerLabel = l
							}
						}
					}
				}
				writer.WriteString(fmt.Sprintf("[%s] 【スーパーステッカー (%s)】 %s: [%s]\n", ts, amount, author, stickerLabel))
				counts["sticker"]++
			case "gift_buy":
				primaryText := ""
				if header, ok := renderer["header"].(map[string]interface{}); ok {
					if hRenderer, ok := header["liveChatSponsorshipsHeaderRenderer"].(map[string]interface{}); ok {
						primaryText = parseRuns(getNestedMap(hRenderer, "primaryText", "runs"))
					}
				}
				writer.WriteString(fmt.Sprintf("[%s] 【メンギフ購入】 %s: %s\n", ts, author, primaryText))
				counts["gift_buy"]++
			case "gift_get":
				msg := parseRuns(getNestedMap(renderer, "message", "runs"))
				writer.WriteString(fmt.Sprintf("[%s] 【メンギフ受取】 %s: %s\n", ts, author, msg))
				counts["gift_get"]++
			case "milestone":
				period := parseRuns(getNestedMap(renderer, "headerPrimaryText", "runs"))
				msg := parseRuns(getNestedMap(renderer, "message", "runs"))
				writer.WriteString(fmt.Sprintf("[%s] 【メンバー継続 (%s)】 %s: %s\n", ts, period, author, msg))
				counts["milestone"]++
			}
		}
	}

	fmt.Println("\n=== 解析完了 ===")
	fmt.Printf("  通常チャット: %d 件\n", counts["text"])
	fmt.Printf("  スパチャ: %d 件\n", counts["superchat"])
	fmt.Printf("  スーパーステッカー: %d 件\n", counts["sticker"])
	fmt.Printf("  メンギフ購入: %d 件\n", counts["gift_buy"])
	fmt.Printf("  メンギフ受取: %d 件\n", counts["gift_get"])
	fmt.Printf("  メンバー継続（コメント付）: %d 件\n", counts["milestone"])
	fmt.Printf("📁 保存先ファイル: %s\n", outputPath)
}

// getNestedMap は map の深い階層から値を安全に取得するためのヘルパー関数です
func getNestedMap(m map[string]interface{}, key1, key2 string) interface{} {
	if val, ok := m[key1].(map[string]interface{}); ok {
		return val[key2]
	}
	return nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("使い方: go run main.go <ファイル名.live_chat.json>")
		os.Exit(1)
	}

	targetJson := os.Args[1]
	ext := filepath.Ext(targetJson)
	outputTxt := strings.TrimSuffix(targetJson, ext) + "_parsed_chat.txt"
	parseLiveChat(targetJson, outputTxt)
}
