package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// UserStat ユーザーごとの統計情報を保持する構造体
type UserStat struct {
	UserName  string
	Comments  int
	SuperChat int
}

func main() {
	// コマンドライン引数のチェック
	if len(os.Args) < 2 {
		fmt.Println("使い方: go run main.go <チャットデータのファイル名>")
		fmt.Println("例: go run main.go chat.txt")
		os.Exit(1)
	}

	inputFilename := os.Args[1]
	// 拡張子を除いたファイル名に _result.txt を付与
	ext := filepath.Ext(inputFilename)
	outputFilename := strings.TrimSuffix(inputFilename, ext) + "_result.txt"

	// ユーザー名 -> 統計データのマップ
	userStats := make(map[string]*UserStat)

	// 正規表現のコンパイル
	// スパチャとスーパーステッカーをまとめて判定する正規表現
	rePaidMsg := regexp.MustCompile(`【(スパチャ|スーパーステッカー)\s*\(¥(\d+)\)】\s*@(\S+):`)
	reMember := regexp.MustCompile(`【メンバー継続[^】]*】\s*@([^:]+):`)
	reComment := regexp.MustCompile(`\[.*?\]\s*@([^:]+):`)

	file, err := os.Open(inputFilename)
	if err != nil {
		fmt.Printf("エラー: 入力ファイル '%s' が見つかりません。\n", inputFilename)
		os.Exit(1)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var user string
		var amount int

		// 1. スパチャ / スーパーステッカー の判定
		if match := rePaidMsg.FindStringSubmatch(line); match != nil {
			// match[1]は種別(スパチャ/ステッカー), [2]は金額, [3]はユーザー名
			amount, _ = strconv.Atoi(match[2])
			user = match[3]
			updateStats(userStats, user, 1, amount)
			continue
		}

		// 2. メンバー継続行の判定 (書き込み数にカウント)
		if match := reMember.FindStringSubmatch(line); match != nil {
			user = strings.TrimSpace(match[1])
			updateStats(userStats, user, 1, 0)
			continue
		}

		// ※ 新規メンバー加入はここで判定せず、単に無視することで「カウントなし」を実現

		// 3. 通常コメント行の判定
		if match := reComment.FindStringSubmatch(line); match != nil {
			user = strings.TrimSpace(match[1])
			updateStats(userStats, user, 1, 0)
		}
	}

	// ソート用のスライスに変換
	var sortedUsers []*UserStat
	for _, stat := range userStats {
		sortedUsers = append(sortedUsers, stat)
	}

	// 総合ランキングのソート
	// 優先度1: スパチャ合計額（降順）、優先度2: 書き込み回数（降順）
	sort.Slice(sortedUsers, func(i, j int) bool {
		if sortedUsers[i].SuperChat != sortedUsers[j].SuperChat {
			return sortedUsers[i].SuperChat > sortedUsers[j].SuperChat
		}
		return sortedUsers[i].Comments > sortedUsers[j].Comments
	})

	// 出力テキストの作成
	var output strings.Builder
	output.WriteString(fmt.Sprintf("%-16s | %-10s | %-10s\n", "ユーザー名", "書き込み回数", "スパチャ合計"))
	output.WriteString(strings.Repeat("-", 46) + "\n")

	for _, s := range sortedUsers {
		// ¥金額部分は簡易的に右寄せで出力
		output.WriteString(fmt.Sprintf("@%-15s | %6d回      | ¥%7d\n", s.UserName, s.Comments, s.SuperChat))
	}

	resultText := output.String()

	// 結果をファイルに保存
	err = os.WriteFile(outputFilename, []byte(resultText), 0644)
	if err != nil {
		fmt.Printf("エラー: ファイル書き込みに失敗しました: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("集計が完了しました。結果を '%s' に保存しました。\n", outputFilename)
	fmt.Printf("\n--- 集計結果プレビュー ---\n%s", resultText)
}

// updateStats マップを更新するヘルパー関数
func updateStats(stats map[string]*UserStat, user string, commentCount, scAmount int) {
	if _, ok := stats[user]; !ok {
		stats[user] = &UserStat{UserName: user}
	}
	stats[user].Comments += commentCount
	stats[user].SuperChat += scAmount
}
