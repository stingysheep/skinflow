param(
  [string]$Output = "$PSScriptRoot\..\assets\skinflow.ico"
)

Add-Type -AssemblyName System.Drawing

function Add-RoundedRect {
  param($Path, [float]$X, [float]$Y, [float]$Width, [float]$Height, [float]$Radius)
  $diameter = $Radius * 2
  $Path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
  $Path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
  $Path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
  $Path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
  $Path.CloseFigure()
}

$sizes = @(16, 24, 32, 48, 64, 128, 256)
$frames = @()

foreach ($size in $sizes) {
  $bitmap = New-Object System.Drawing.Bitmap $size, $size
  $bitmap.SetResolution(96, 96)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.Clear([System.Drawing.Color]::Transparent)

  $scale = $size / 256.0
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  Add-RoundedRect $path (8 * $scale) (8 * $scale) (240 * $scale) (240 * $scale) (48 * $scale)
  $graphics.FillPath((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 17, 24, 32))), $path)
  $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 92, 224, 210)), (18 * $scale)
  $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  $points = @(
    (New-Object System.Drawing.PointF (55 * $scale), (151 * $scale)),
    (New-Object System.Drawing.PointF (91 * $scale), (112 * $scale)),
    (New-Object System.Drawing.PointF (126 * $scale), (139 * $scale)),
    (New-Object System.Drawing.PointF (184 * $scale), (79 * $scale))
  )
  $graphics.DrawLines($pen, $points)
  $graphics.DrawLine($pen, (158 * $scale), (79 * $scale), (184 * $scale), (79 * $scale))
  $graphics.DrawLine($pen, (184 * $scale), (79 * $scale), (184 * $scale), (105 * $scale))
  $nodeBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 61, 141, 245))
  foreach ($point in @(@(55,151), @(126,139), @(184,79))) {
    $diameter = 24 * $scale
    $graphics.FillEllipse($nodeBrush, (($point[0] * $scale) - ($diameter / 2)), (($point[1] * $scale) - ($diameter / 2)), $diameter, $diameter)
  }
  $stream = New-Object System.IO.MemoryStream
  $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
  $frames += ,@($size, $stream.ToArray())
  $stream.Dispose(); $graphics.Dispose(); $bitmap.Dispose(); $path.Dispose(); $pen.Dispose(); $nodeBrush.Dispose()
}

$directorySize = 6 + (16 * $frames.Count)
$offset = $directorySize
$outputStream = [System.IO.File]::Open($Output, [System.IO.FileMode]::Create)
$writer = New-Object System.IO.BinaryWriter $outputStream
$writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$frames.Count)
foreach ($frame in $frames) {
  $size = [int]$frame[0]; $bytes = [byte[]]$frame[1]
  $writer.Write([byte]($(if ($size -eq 256) { 0 } else { $size })))
  $writer.Write([byte]$(if ($size -eq 256) { 0 } else { $size }))
  $writer.Write([byte]0); $writer.Write([byte]0); $writer.Write([uint16]1); $writer.Write([uint16]32)
  $writer.Write([uint32]$bytes.Length); $writer.Write([uint32]$offset)
  $offset += $bytes.Length
}
foreach ($frame in $frames) { $writer.Write([byte[]]$frame[1]) }
$writer.Dispose(); $outputStream.Dispose()
Write-Output "Generated $Output"
