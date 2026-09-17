Add-Type -AssemblyName System.Windows.Forms

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ScoreBugWindow {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    private static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int index);
    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
    private static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int index, IntPtr value);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongW")]
    private static extern int GetWindowLong32(IntPtr hWnd, int index);
    [DllImport("user32.dll", EntryPoint = "SetWindowLongW")]
    private static extern int SetWindowLong32(IntPtr hWnd, int index, int value);
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr extraData);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int maxCount);
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr extraData);
    public static IntPtr FindByTitle(string title) {
        IntPtr result = IntPtr.Zero;
        EnumWindows((hWnd, extraData) => {
            var text = new System.Text.StringBuilder(256);
            GetWindowText(hWnd, text, text.Capacity);
            if (text.ToString().IndexOf(title, StringComparison.OrdinalIgnoreCase) >= 0) {
                result = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }
    public static void RemoveFrame(IntPtr hWnd) {
        const int GWL_STYLE = -16;
        const long WS_CAPTION = 0x00C00000L;
        const long WS_THICKFRAME = 0x00040000L;
        const long WS_MINIMIZEBOX = 0x00020000L;
        const long WS_MAXIMIZEBOX = 0x00010000L;
        const long WS_SYSMENU = 0x00080000L;
        long style = IntPtr.Size == 8 ? GetWindowLongPtr(hWnd, GWL_STYLE).ToInt64() : GetWindowLong32(hWnd, GWL_STYLE);
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU);
        if (IntPtr.Size == 8) { SetWindowLongPtr(hWnd, GWL_STYLE, new IntPtr(style)); }
        else { SetWindowLong32(hWnd, GWL_STYLE, (int)style); }
        SetWindowPos(hWnd, IntPtr.Zero, 0, 0, 0, 0, 0x27);
    }
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
}
'@

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $root 'ScoreBugOverlay.html'
$url = 'file:///' + ($html -replace '\\', '/')
$profile = Join-Path $env:TEMP ("ScoreBugOverlay-" + [guid]::NewGuid().ToString('N'))
$arguments = "--user-data-dir=`"$profile`" --app=`"$url`" --window-size=1600,105 --window-position=0,900"

$browserPaths = @(
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
)
$browser = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) {
    [System.Windows.Forms.MessageBox]::Show('Microsoft Edge or Google Chrome was not found.', 'ScoreBug')
    exit 1
}

$browserProcess = Start-Process -FilePath $browser -ArgumentList $arguments -PassThru
try { $browserProcess.WaitForInputIdle(5000) | Out-Null } catch { }

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $windowHandle = [ScoreBugWindow]::FindByTitle('ScoreBug Overlay')
    if ($windowHandle -ne [IntPtr]::Zero) {
        [ScoreBugWindow]::RemoveFrame($windowHandle)
        [ScoreBugWindow]::SetWindowPos(
            $windowHandle,
            [ScoreBugWindow]::HWND_TOPMOST,
            $screen.Left,
            ($screen.Bottom - 105),
            $screen.Width,
            105,
            0x50
        ) | Out-Null
    }
    [System.Threading.Thread]::Sleep(250)
}
