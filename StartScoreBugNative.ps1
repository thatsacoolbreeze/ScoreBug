Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class ScoreBugNative {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindow(string className, string windowName);
    [DllImport("user32.dll")]
    public static extern IntPtr SetParent(IntPtr child, IntPtr parent);
    [DllImport("user32.dll")]
    public static extern bool MoveWindow(IntPtr handle, int x, int y, int width, int height, bool repaint);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr handle, int command);
    public const int SW_SHOW = 5;
}
'@

[System.Windows.Forms.Application]::EnableVisualStyles()
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $root 'ScoreBugOverlay.html'
$url = 'file:///' + ($html -replace '\\', '/')
$profile = Join-Path $env:TEMP ("ScoreBugNative-" + [guid]::NewGuid().ToString('N'))

$browser = @(
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { [System.Windows.Forms.MessageBox]::Show('Microsoft Edge or Google Chrome was not found.', 'ScoreBug'); exit 1 }

$arguments = "--user-data-dir=`"$profile`" --app=`"$url`" --window-size=1600,105"
Start-Process -FilePath $browser -ArgumentList $arguments | Out-Null

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$hostForm = New-Object System.Windows.Forms.Form
$hostForm.Text = 'ScoreBug Native Overlay'
$hostForm.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$hostForm.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$hostForm.Location = New-Object System.Drawing.Point($screen.Left, ($screen.Bottom - 105))
$hostForm.ClientSize = New-Object System.Drawing.Size($screen.Width, 105)
$hostForm.TopMost = $true
$hostForm.ShowInTaskbar = $false
$hostForm.BackColor = [System.Drawing.Color]::Black

$hostForm.Add_Shown({
    $timer.Start()
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 250
$attempts = 0
$timer.Add_Tick({
    $script:attempts++
    $child = [ScoreBugNative]::FindWindow($null, 'ScoreBug Overlay')
    if ($child -ne [IntPtr]::Zero) {
        [ScoreBugNative]::SetParent($child, $hostForm.Handle) | Out-Null
        [ScoreBugNative]::MoveWindow($child, 0, 0, $screen.Width, 105, $true) | Out-Null
        [ScoreBugNative]::ShowWindow($child, [ScoreBugNative]::SW_SHOW) | Out-Null
        $timer.Stop()
    } elseif ($script:attempts -ge 20) {
        $timer.Stop()
        $hostForm.Close()
    }
})

$hostForm.Add_FormClosed({
    $timer.Stop()
})

[void]$hostForm.ShowDialog()
