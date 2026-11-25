REM 複数の候補から優先順位をつけて選ぶ（フォールバック）動画によっては指定した itag（例: 774 や 251）が存在しないこともあるため、/ で繋いで優先順位を付けられます。

REM -o（--output）を使うと、保存先のディレクトリやファイル名テンプレートを指定できます（確信度: 95%）。
REM yt-dlp -f 251 -o "%(title)s [%(id)s].%(ext)s" "https://www.youtube.com/watch?v=XXXXXXXXXXX"

yt-dlp -f 139 "https://www.youtube.com/watch?v=KUiG4TnP3Ls&"
REM yt-dlp -f 251 "https://www.youtube.com/watch?v=Rx_tFJxakxk"

pause