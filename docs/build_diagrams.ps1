$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$diagramDirectory = Join-Path $PSScriptRoot 'diagrams'
[IO.Directory]::CreateDirectory($diagramDirectory) | Out-Null
$ink = '#203747'; $muted = '#526675'; $accent = '#0B7770'; $paper = '#F5F8FA'

function Start-Diagram([int]$height) {
    $script:canvasHeight = $height
    $script:bitmap = [Drawing.Bitmap]::new(1200, $height)
    $script:graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.Clear([Drawing.Color]::White)
    $script:svg = [Text.StringBuilder]::new()
    [void]$svg.AppendLine("<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='$height' viewBox='0 0 1200 $height' role='img'><rect width='1200' height='$height' fill='white'/>")
}
function Label($text, $x, $y, $width, $height, $size=26, $bold=$false, $center=$true, $color=$ink) {
    $fontStyle = if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
    $font = [Drawing.Font]::new('Arial', [single]$size, $fontStyle, [Drawing.GraphicsUnit]::Pixel)
    $brush = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($color))
    $format = [Drawing.StringFormat]::new()
    $format.Alignment = if ($center) { [Drawing.StringAlignment]::Center } else { [Drawing.StringAlignment]::Near }
    $format.LineAlignment = [Drawing.StringAlignment]::Center
    $format.FormatFlags = [Drawing.StringFormatFlags]::LineLimit
    $wrapped = [Collections.Generic.List[string]]::new()
    foreach ($explicitLine in ($text -split "`n")) {
        $current = ''
        foreach ($word in ($explicitLine -split ' ' | Where-Object { $_ })) {
            $candidate = if($current){"$current $word"}else{$word}
            if($current -and $graphics.MeasureString($candidate,$font).Width -gt $width) {
                $wrapped.Add($current); $current=$word
            } else {$current=$candidate}
        }
        $wrapped.Add($current)
    }
    $lines = $wrapped.ToArray()
    if($lines.Count*$size*1.25 -gt $height) {
        Write-Warning "Text box needs more height: $text"
    }
    $baseline = $y + ($height - $lines.Count * $size * 1.25) / 2 + $size
    $anchor = if ($center) { 'middle' } else { 'start' }
    $textX = if ($center) { $x+$width/2 } else { $x }
    $weight = if ($bold) { '700' } else { '400' }
    foreach ($line in $lines) {
        $lineY = $baseline-$size
        $graphics.DrawString($line,$font,$brush,[Drawing.RectangleF]::new($x,$lineY,$width,($size*1.25)),$format)
        $escaped = [Security.SecurityElement]::Escape($line)
        [void]$svg.AppendLine("<text x='$textX' y='$baseline' text-anchor='$anchor' font-family='Arial, sans-serif' font-size='$size' font-weight='$weight' fill='$color'>$escaped</text>")
        $baseline += $size*1.25
    }
    $format.Dispose(); $brush.Dispose(); $font.Dispose()
}
function Box($x,$y,$w,$h,$text,$fill=$paper,$size=26,$bold=$false) {
    $brush=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($fill))
    $pen=[Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($ink),2)
    $graphics.FillRectangle($brush,$x,$y,$w,$h); $graphics.DrawRectangle($pen,$x,$y,$w,$h)
    [void]$svg.AppendLine("<rect x='$x' y='$y' width='$w' height='$h' fill='$fill' stroke='$ink' stroke-width='2'/>")
    if($text){Label $text ($x+16) ($y+10) ($w-32) ($h-20) $size $bold}
    $brush.Dispose(); $pen.Dispose()
}
function Line($points,$arrow=$false,$dashed=$false,$color=$muted) {
    $pen=[Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($color),2.5)
    if($dashed){$pen.DashStyle=[Drawing.Drawing2D.DashStyle]::Dash}
    $coords=[Drawing.PointF[]]@($points | ForEach-Object { [Drawing.PointF]::new($_[0],$_[1]) })
    $graphics.DrawLines($pen,$coords)
    $stringPoints=($points | ForEach-Object { "$($_[0]),$($_[1])" }) -join ' '
    $dash=if($dashed){"stroke-dasharray='8 6'"}else{''}
    [void]$svg.AppendLine("<polyline points='$stringPoints' fill='none' stroke='$color' stroke-width='2.5' $dash/>")
    if($arrow){
        $a=$coords[-2];$b=$coords[-1];$angle=[Math]::Atan2($b.Y-$a.Y,$b.X-$a.X)
        $p1=[Drawing.PointF]::new($b.X-13*[Math]::Cos($angle-0.45),$b.Y-13*[Math]::Sin($angle-0.45))
        $p2=[Drawing.PointF]::new($b.X-13*[Math]::Cos($angle+0.45),$b.Y-13*[Math]::Sin($angle+0.45))
        $triangle=[Drawing.PointF[]]@($b,$p1,$p2);$brush=[Drawing.SolidBrush]::new($pen.Color)
        $graphics.FillPolygon($brush,$triangle)
        [void]$svg.AppendLine("<polygon points='$($b.X),$($b.Y) $($p1.X),$($p1.Y) $($p2.X),$($p2.Y)' fill='$color'/>")
        $brush.Dispose()
    }
    $pen.Dispose()
}
function Oval($x,$y,$w,$h,$text,$fill='white',$size=25) {
    $brush=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($fill));$pen=[Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($ink),2)
    $graphics.FillEllipse($brush,$x,$y,$w,$h);$graphics.DrawEllipse($pen,$x,$y,$w,$h)
    [void]$svg.AppendLine("<ellipse cx='$($x+$w/2)' cy='$($y+$h/2)' rx='$($w/2)' ry='$($h/2)' fill='$fill' stroke='$ink' stroke-width='2'/>")
    if($text){Label $text ($x+25) ($y+8) ($w-50) ($h-16) $size}
    $brush.Dispose();$pen.Dispose()
}
function Diamond($cx,$cy,$w,$h,$text) {
    $points=@(@($cx,($cy-$h/2)),@(($cx+$w/2),$cy),@($cx,($cy+$h/2)),@(($cx-$w/2),$cy),@($cx,($cy-$h/2)))
    $polygon=[Drawing.PointF[]]@($points | ForEach-Object {[Drawing.PointF]::new($_[0],$_[1])})
    $brush=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml('#E8F4F1'))
    $graphics.FillPolygon($brush,$polygon)
    $stringPoints=($points|ForEach-Object{"$($_[0]),$($_[1])"})-join ' '
    [void]$svg.AppendLine("<polygon points='$stringPoints' fill='#E8F4F1'/>")
    Line $points
    Label $text ($cx-$w/3) ($cy-$h/3) ($w*2/3) ($h*2/3) 25
    $brush.Dispose()
}
function Finish-Diagram($name) {
    [void]$svg.AppendLine('</svg>')
    [IO.File]::WriteAllText((Join-Path $diagramDirectory "$name.svg"),$svg.ToString(),[Text.UTF8Encoding]::new($false))
    $bitmap.Save((Join-Path $diagramDirectory "$name.png"),[Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose();$bitmap.Dispose()
    Write-Output "Created $name (SVG + PNG)."
}

# Deployment: application traffic and release-time tasks are deliberately distinct.
Start-Diagram 920
Box 40 45 350 115 "Student / staff`nPhone / desktop" '#E8F4F1' 26 $true
Box 40 230 700 180 ''
Label 'Frontend - Vercel' 55 248 670 40 30 $true
Label "React / Vite: student and admin portals`nStatic assets served by CDN`n/api/* stays on the browser's origin" 65 295 650 100 26
Line @(@(215,160),@(215,230)) $true
Label 'HTTPS' 230 167 120 40 24
Box 40 515 700 185 ''
Label 'Backend - Vercel Python / WSGI' 55 535 670 40 29 $true
Label "Django REST Framework`nValidation, search, analytics and CSV`nStaff sessions + CSRF checks" 65 580 650 100 26
Line @(@(390,410),@(390,515)) $true
Label '/api/* and DRF static proxy' 405 440 315 40 24
Box 825 520 335 180 "Neon PostgreSQL`nCourses / events`nStudents / inquiries`nUsers / sessions" '#E8F4F1' 27 $true
Line @(@(740,605),@(825,605)) $true
Label 'TLS / pooled connection' 750 440 430 60 24
Box 830 45 330 160 "GitHub repositories`nFrontend and backend`nPush triggers deployment" 'white' 26
Line @(@(830,160),@(780,160),@(780,280),@(740,280)) $true $true
Line @(@(780,280),@(780,560),@(740,560)) $true $true
Box 40 780 700 95 "Release / migration scripts`nRun once with hosted database credentials" 'white' 26
Line @(@(740,825),@(990,825),@(990,700)) $true $true
Label "Release tasks`nDirect connection" 765 725 210 70 23
Finish-Diagram 'architecture'

# Domain classes reflect actual Django model fields, not proposed staff assignment.
function Draw-Class($x,$y,$w,$h,$name,$fields) {
    Box $x $y $w $h '' 'white'
    Box $x $y $w 55 $name '#E8F4F1' 28 $true
    Label $fields ($x+20) ($y+70) ($w-40) ($h-85) 25 $false $false
}
Start-Diagram 1240
Draw-Class 35 40 465 290 'Student' "id: PK`nemail: case-insensitive unique`nfull_name, phone, location`ncreated_at, updated_at"
Draw-Class 700 40 465 290 'Course' "id: PK`nname, level, location`nprice: Decimal (NGN)`nintakes: JSON; active: Boolean"
Draw-Class 350 435 510 395 'Inquiry' "id: PK; reference: unique`nstudent_id, course_id, event_id: FK`nfull_name, email, phone: snapshot`nintake, destination, student_location`nmessage, internal_notes`nstatus: New / Contacted /`n          Converted / Closed`ncreated_at"
Draw-Class 35 900 465 285 'Event' "id: PK`nname, city, venue`ndate, time`ncapacity: positive integer"
Draw-Class 700 930 465 255 'User (Django auth)' "id: PK; username: unique`npassword: hashed`nis_staff, is_superuser, is_active`ngroups, user_permissions"
Line @(@(267,330),@(267,480),@(350,480))
Label '1' 220 342 70 40 26
Label '0..*' 272 435 80 40 25
Line @(@(932,330),@(932,480),@(860,480))
Label '1' 940 342 65 40 26
Label '0..*' 856 435 80 40 25
Line @(@(267,900),@(267,780),@(350,780))
Label '1' 220 843 70 40 26
Label '0..*' 272 785 80 40 25
Label "Each inquiry has exactly one student, course and event.`nUser authorizes staff access; there is no inquiry-owner FK." 300 837 850 55 22 $false $true $muted
Finish-Diagram 'class'

function Actor($x,$y,$name) {
    Oval ($x-19) ($y-55) 38 38 '' 'white'
    Line @(@($x,($y-17)),@($x,($y+55)))
    Line @(@(($x-40),($y+12)),@(($x+40),($y+12)))
    Line @(@($x,($y+55)),@(($x-35),($y+103)))
    Line @(@($x,($y+55)),@(($x+35),($y+103)))
    Label $name ($x-65) ($y+105) 130 55 25 $true
}
Start-Diagram 1050
Box 165 40 870 905 '' 'white'
Label 'Student Portal' 200 55 800 45 30 $true
Actor 70 375 'Student'
Actor 1130 570 'Staff'
$studentCases=@(@('Search / filter courses',245),@("View fees and intakes",395),@("Submit interest`n(optional message)",545),@("See confirmation`nand reference",695))
foreach($case in $studentCases){Line @(@(110,387),@(230,($case[1]+42))); Oval 230 $case[1] 335 85 $case[0] '#F5F8FA' 25}
$staffCases=@(@('Sign in / sign out',135),@('Manage courses',245),@('Manage events',355),@("Search / filter /`nopen inquiries",465),@("Update status`nand internal notes",575),@("View dashboard`nand reports",685),@('Export filtered CSV',795))
foreach($case in $staffCases){Line @(@(1090,582),@(985,($case[1]+42))); Oval 650 $case[1] 335 85 $case[0] '#E8F4F1' 25}
Label "Staff actions require an authenticated session; sign-in is the exception.`nStudents do not need an account. Separate specialist staff roles are not implemented." 80 960 1040 70 23 $false $true $muted
Finish-Diagram 'use-case'

# Submission flow includes both validation loops and the duplicate-reference branch.
Start-Diagram 1320
Label 'Student / browser' 80 15 430 45 28 $true
Label 'Django API / PostgreSQL' 680 15 450 45 28 $true
Line @(@(600,75),@(600,1300)) $false $true '#D7E0E5'
Oval 245 72 30 30 '' $ink
Line @(@(260,102),@(260,140)) $true
Box 85 140 350 105 "Search / choose course`nComplete inquiry form" '#F5F8FA' 26
Line @(@(260,245),@(260,290)) $true
Diamond 260 355 250 130 'Client valid?'
Line @(@(135,355),@(45,355),@(45,190),@(85,190)) $true
Label 'No: fix form' 55 256 160 35 20
Line @(@(260,420),@(260,475)) $true
Label 'Yes' 270 429 70 35 23
Box 85 475 350 85 'POST /api/inquiries/' 'white' 26
Line @(@(435,517),@(710,517)) $true
Box 710 475 365 85 "Validate fields, course,`nintake and upcoming event" '#E8F4F1' 25
Line @(@(892,560),@(892,610)) $true
Diamond 892 680 265 140 'Server valid?'
Line @(@(760,680),@(645,680),@(645,265),@(450,265),@(450,215),@(435,215)) $true
Label "No: return errors`nHTTP 400; correct form" 655 300 385 75 24
Line @(@(892,750),@(892,800)) $true
Label 'Yes' 900 755 80 35 23
Box 710 800 365 90 "Normalize email; get student`nLock row in transaction" '#E8F4F1' 24
Line @(@(892,890),@(892,935)) $true
Label "Same student,`ncourse + event" 620 900 210 85 22
Diamond 892 1005 285 140 "Repeat within`n24 hours?"
Line @(@(750,1005),@(460,1005)) $true
Label 'Yes' 550 961 100 35 23
Box 100 965 360 85 "Reuse existing reference`nHTTP 200; duplicate = true" 'white' 24
Line @(@(280,1050),@(280,1160)) $true
Line @(@(892,1075),@(892,1120)) $true
Label 'No' 905 1080 75 35 23
Box 710 1120 365 110 "Create inquiry + reference`nCommit transaction`nHTTP 201" '#E8F4F1' 22
Line @(@(710,1170),@(530,1170),@(530,1200),@(460,1200)) $true
Box 100 1160 360 90 "Show confirmation`nand reference number" '#F5F8FA' 26
Line @(@(280,1250),@(280,1280)) $true
Oval 265 1280 30 30 '' 'white'
Oval 272 1287 16 16 '' $ink
Finish-Diagram 'activity'
