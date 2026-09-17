Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$settingsPath = Join-Path $scriptRoot 'ScoreBug.html'
$selectedDate = (Get-Date).ToString('yyyy-MM-dd')
$scrollSpeed = 3
$scrollOffset = 0
$scoresText = 'Loading scores...'

$feeds = @(
    @{ Name = 'NFL'; Url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard' },
    @{ Name = 'NHL'; Url = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard' },
    @{ Name = 'NCAA FB'; Url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard' }
)

function Get-ScoreText {
    $dateQuery = $script:selectedDate.Replace('-', '')
    $items = New-Object System.Collections.Generic.List[string]
    $failedFeeds = New-Object System.Collections.Generic.List[string]

    foreach ($feed in $feeds) {
        try {
            $requestUrl = "$($feed.Url)?dates=$dateQuery"
            try {
                $data = Invoke-RestMethod -Uri $requestUrl -Headers @{ 'User-Agent' = 'Mozilla/5.0' } -TimeoutSec 15
            } catch {
                $proxyUrl = "https://r.jina.ai/http://$($feed.Url.Substring(8))?dates=$dateQuery"
                $proxyResponse = Invoke-WebRequest -Uri $proxyUrl -Headers @{ 'User-Agent' = 'Mozilla/5.0' } -UseBasicParsing -TimeoutSec 20
                $data = $proxyResponse.Content | ConvertFrom-Json
            }
            foreach ($event in @($data.events)) {
                $competition = $event.competitions[0]
                $home = @($competition.competitors | Where-Object { $_.homeAway -eq 'home' })[0]
                $away = @($competition.competitors | Where-Object { $_.homeAway -eq 'away' })[0]
                $detail = $event.status.type.shortDetail
                if ([string]::IsNullOrWhiteSpace($detail)) { $detail = $event.status.type.description }
                $items.Add("$($feed.Name): $($away.team.abbreviation) $($away.score) - $($home.team.abbreviation) $($home.score) [$detail]")
            }
        } catch {
            $failedFeeds.Add($feed.Name)
        }
    }

    if ($items.Count -eq 0 -and $failedFeeds.Count -gt 0) {
        return "Score feed unavailable for $script:selectedDate"
    }
    if ($items.Count -eq 0) { return "No games found for $script:selectedDate" }
    return ($items -join '     |     ') + '     |     '
}

function Open-Settings {
    $settings = New-Object System.Windows.Forms.Form
    $settings.Text = 'ScoreBug Settings'
    $settings.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $settings.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $settings.ClientSize = New-Object System.Drawing.Size(360, 145)
    $settings.MaximizeBox = $false
    $settings.MinimizeBox = $false
    $settings.TopMost = $true

    $dateLabel = New-Object System.Windows.Forms.Label
    $dateLabel.Text = 'Sports date:'
    $dateLabel.AutoSize = $true
    $dateLabel.Location = New-Object System.Drawing.Point(18, 20)
    $settings.Controls.Add($dateLabel)

    $datePicker = New-Object System.Windows.Forms.DateTimePicker
    $datePicker.Format = [System.Windows.Forms.DateTimePickerFormat]::Short
    $datePicker.Value = [datetime]::Parse($script:selectedDate)
    $datePicker.Location = New-Object System.Drawing.Point(112, 16)
    $settings.Controls.Add($datePicker)

    $apply = New-Object System.Windows.Forms.Button
    $apply.Text = 'Apply and refresh'
    $apply.AutoSize = $true
    $apply.Location = New-Object System.Drawing.Point(112, 58)
    $apply.Add_Click({
        $script:selectedDate = $datePicker.Value.ToString('yyyy-MM-dd')
        $script:scoresText = Get-ScoreText
        $label.Text = $script:scoresText
        $script:scrollOffset = $form.Width
        $settings.Close()
    })
    $settings.Controls.Add($apply)

    $openFull = New-Object System.Windows.Forms.LinkLabel
    $openFull.Text = 'Open full browser settings'
    $openFull.AutoSize = $true
    $openFull.Location = New-Object System.Drawing.Point(112, 100)
    $openFull.Add_Click({
        if (Get-Command msedge.exe -ErrorAction SilentlyContinue) {
            $fileUrl = 'file:///' + ($settingsPath -replace '\\', '/')
            Start-Process msedge.exe "--app=$fileUrl --window-size=1100,700"
        } else {
            Start-Process $settingsPath
        }
    })
    $settings.Controls.Add($openFull)

    [void]$settings.ShowDialog()
}

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.TopMost = $true
$form.ShowInTaskbar = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(12, 18, 22)
$form.ForeColor = [System.Drawing.Color]::White
$form.Height = 58
$form.Width = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Width
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point($workArea.Left, ($workArea.Bottom - $form.Height))
$form.Cursor = [System.Windows.Forms.Cursors]::Hand

$accent = New-Object System.Windows.Forms.Panel
$accent.Dock = [System.Windows.Forms.DockStyle]::Top
$accent.Height = 4
$accent.BackColor = [System.Drawing.Color]::FromArgb(225, 6, 0)
$form.Controls.Add($accent)

$label = New-Object System.Windows.Forms.Label
$label.AutoSize = $true
$label.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
$label.ForeColor = [System.Drawing.Color]::White
$label.Text = '  LOADING SCORES...  '
$label.Top = 17
$label.Left = 20
$label.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($label)

$hint = New-Object System.Windows.Forms.Label
$hint.AutoSize = $true
$hint.Text = '  CLICK FOR SETTINGS'
$hint.Font = New-Object System.Drawing.Font('Segoe UI', 8, [System.Drawing.FontStyle]::Bold)
$hint.ForeColor = [System.Drawing.Color]::FromArgb(160, 175, 180)
$hint.Anchor = [System.Windows.Forms.AnchorStyles]::Right
$hint.Left = $form.Width - 145
$hint.Top = 21
$hint.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($hint)

$openHandler = { Open-Settings }
$form.Add_Click($openHandler)
$label.Add_Click($openHandler)
$hint.Add_Click($openHandler)
$accent.Add_Click($openHandler)

$refreshTimer = New-Object System.Windows.Forms.Timer
$refreshTimer.Interval = 45000
$refreshTimer.Add_Tick({
    $script:scoresText = Get-ScoreText
    $label.Text = $script:scoresText
    $script:scrollOffset = $form.Width
})

$scrollTimer = New-Object System.Windows.Forms.Timer
$scrollTimer.Interval = 35
$scrollTimer.Add_Tick({
    $script:scrollOffset -= $scrollSpeed
    if ($script:scrollOffset -lt -$label.Width) { $script:scrollOffset = $form.Width }
    $label.Left = $script:scrollOffset
})

$initialLoadTimer = New-Object System.Windows.Forms.Timer
$initialLoadTimer.Interval = 250
$initialLoadTimer.Add_Tick({
    $initialLoadTimer.Stop()
    $script:scoresText = Get-ScoreText
    $label.Text = $script:scoresText
    $script:scrollOffset = $form.Width
})

$form.Add_Shown({
    $scrollTimer.Start()
    $refreshTimer.Start()
    $script:initialLoadTimer.Start()
})

$form.Add_FormClosed({
    $refreshTimer.Stop()
    $scrollTimer.Stop()
})

[void]$form.ShowDialog()
