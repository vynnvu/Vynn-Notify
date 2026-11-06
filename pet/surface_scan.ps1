$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
while ($null -ne ($line = [Console]::ReadLine())) {
    $result = @()
    try {
        $targets = $line | ConvertFrom-Json
        foreach ($target in $targets) {
            try {
                $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$target)
                $area = $root.Current.BoundingRectangle
                $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::IsOffscreenProperty, $false)
                $cache = New-Object System.Windows.Automation.CacheRequest
                $cache.Add([System.Windows.Automation.AutomationElement]::BoundingRectangleProperty)
                $cache.Add([System.Windows.Automation.AutomationElement]::ControlTypeProperty)
                $activation = $cache.Activate()
                try {
                    $elements = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
                } finally { $activation.Dispose() }
                $items = @()
                for ($i = 0; $i -lt $elements.Count -and $items.Count -lt 240; $i++) {
                    try {
                        $element = $elements.Item($i)
                        $current = $element.Cached
                        $kind = $current.ControlType.ProgrammaticName.Replace('ControlType.', '').ToLowerInvariant()
                        if ($kind -notin @('button','combobox','edit','image','listitem','list','tab','tabitem','toolbar','treeitem','document','group','pane')) { continue }
                        $r = $current.BoundingRectangle
                        if ($r.IsEmpty -or $r.Width -lt 24 -or $r.Height -lt 6 -or $r.Width * $r.Height -ge $area.Width * $area.Height * 0.95) { continue }
                        $items += @{id=($element.GetRuntimeId() -join '.'); kind=$kind; x=$r.Left; y=$r.Top; w=$r.Width; h=$r.Height}
                    } catch { }
                }
                $result += @{hwnd=[long]$target; x=$area.Left; y=$area.Top; w=$area.Width; h=$area.Height; items=@($items)}
            } catch { }
        }
    } catch { }
    $json = ConvertTo-Json -InputObject @($result) -Depth 5 -Compress
    [Console]::WriteLine($json)
    [Console]::Out.Flush()
}
