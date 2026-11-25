package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
)

func cleanLrc(inputPath, outputPath string) error {
	// タイムスタンプとテキスト部分を分離するための正規表現
	// Pythonの r'^(\[\d+:\d{2}(?:\.\d+)?\])(.*)$' と同等
	pattern := regexp.MustCompile(`^(\[\d+:\d{2}(?:\.\d+)?\])(.*)$`)

	inputFile, err := os.Open(inputPath)
	if err != nil {
		return err
	}
	defer inputFile.Close()

	var cleanedLines []string
	var prevText string

	scanner := bufio.NewScanner(inputFile)
	for scanner.Scan() {
		line := scanner.Text()
		stripped := strings.TrimSpace(line)
		if stripped == "" {
			continue
		}

		match := pattern.FindStringSubmatch(stripped)
		if match != nil {
			// match[0]は全体、match[1]がタイムスタンプ、match[2]がテキスト
			text := strings.TrimSpace(match[2])

			// 条件1: 時間表示だけの行（テキストが空）は削除
			if text == "" {
				continue
			}

			// 条件2: 直前の行とテキストが重複している場合は削除
			if text == prevText {
				continue
			}

			cleanedLines = append(cleanedLines, stripped)
			prevText = text
		} else {
			// タイムスタンプ形式ではない行はそのまま維持
			cleanedLines = append(cleanedLines, stripped)
		}
	}

	if err := scanner.Err(); err != nil {
		return err
	}

	// 出力ファイルに書き込み
	outputFile, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer outputFile.Close()

	writer := bufio.NewWriter(outputFile)
	for _, line := range cleanedLines {
		_, err := writer.WriteString(line + "\n")
		if err != nil {
			return err
		}
	}
	return writer.Flush()
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("使用法: go run main.go <input_file>")
		os.Exit(1)
	}

	inpfnm := os.Args[1]
	fmt.Printf("入力ファイルネーム: %s\n", inpfnm)

	// 拡張子を除いたファイル名に _lrc.txt を付与
	var outfnm string
	if dotIdx := strings.LastIndex(inpfnm, "."); dotIdx != -1 {
		outfnm = inpfnm[:dotIdx] + "_lrc.txt"
	} else {
		outfnm = inpfnm + "_lrc.txt"
	}
	fmt.Printf("出力ファイルネーム: %s\n", outfnm)

	err := cleanLrc(inpfnm, outfnm)
	if err != nil {
		fmt.Printf("エラーが発生しました: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("LRCファイルのクリーニングが完了しました。")
}
