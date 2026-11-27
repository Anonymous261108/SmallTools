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

// PURCHASE_PATTERN はメンギフ購入のパターンを定義します
// Pythonの re.IGNORECASE は (?i) フラグで実現します
var purchasePattern = regexp.MustCompile(`(?i)【メンギフ購入】\s*@([^:\s]+)\s*:\s*Sent\s+(\d+)\b.*?\bgift memberships?\b`)

type UserCount struct {
	Sender string
	Count  int
}

// aggregateGifts はファイルから送信者ごとの合計数を集計します
func aggregateGifts(inputPath string) ([]UserCount, error) {
	file, err := os.Open(inputPath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	totals := make(map[string]int)
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		matches := purchasePattern.FindStringSubmatch(line)
		if len(matches) >= 3 {
			sender := matches[1]
			count, err := strconv.Atoi(matches[2])
			if err == nil {
				totals[sender] += count
			}
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	// ソートのためにマップをスライスに変換
	var result []UserCount
	for sender, count := range totals {
		result = append(result, UserCount{Sender: sender, Count: count})
	}

	// 送信数の降順、同数の場合は名前の昇順でソート
	sort.Slice(result, func(i, j int) bool {
		if result[i].Count != result[j].Count {
			return result[i].Count > result[j].Count
		}
		return result[i].Sender < result[j].Sender
	})

	return result, nil
}

// writeResult は集計結果をファイルに書き出します
func writeResult(outputPath string, totals []UserCount, originalFileName string) error {
	totalGifts := 0
	for _, uc := range totals {
		totalGifts += uc.Count
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("対象ファイル: %s\n", originalFileName))
	sb.WriteString(fmt.Sprintf("メンギフ合計数: %d個\n", totalGifts))
	sb.WriteString(strings.Repeat("-", 30) + "\n")

	if len(totals) > 0 {
		for _, uc := range totals {
			sb.WriteString(fmt.Sprintf("@%s: %d個\n", uc.Sender, uc.Count))
		}
	} else {
		sb.WriteString("メンギフ購入の記録はありませんでした。\n")
	}

	return os.WriteFile(outputPath, []byte(sb.String()), 0644)
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("使用法: go run main.go <input_file>")
		os.Exit(1)
	}

	targetPath := os.Args[1]
	ext := filepath.Ext(targetPath)
	base := strings.TrimSuffix(targetPath, ext)
	outputPath := base + "_gift_result.txt"

	totals, err := aggregateGifts(targetPath)
	if err != nil {
		fmt.Printf("エラー: %v\n", err)
		os.Exit(1)
	}

	err = writeResult(outputPath, totals, filepath.Base(targetPath))
	if err != nil {
		fmt.Printf("書き出しエラー: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[完了] %s -> %s\n", targetPath, outputPath)
}
