$ErrorActionPreference = "Continue"

$dayz = "C:\Program Files (x86)\Steam\steamapps\common\DayZ"
$launcherExe = Join-Path $dayz "DayZLauncher.exe"
$launcherDir = Join-Path $dayz "Launcher"

[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender, $eventArgs)
    $name = (New-Object System.Reflection.AssemblyName($eventArgs.Name)).Name + ".dll"
    foreach ($candidate in @((Join-Path $launcherDir $name), (Join-Path $dayz $name))) {
        if (Test-Path -LiteralPath $candidate) {
            return [System.Reflection.Assembly]::LoadFrom($candidate)
        }
    }
    return $null
})

$asm = [System.Reflection.Assembly]::LoadFrom($launcherExe)
try {
    $types = $asm.GetTypes()
} catch [System.Reflection.ReflectionTypeLoadException] {
    $types = $_.Exception.Types | Where-Object { $_ }
}

$localIdType = $types | Where-Object { $_.FullName -eq "Launcher.Extensions.Models.LocalAddonIdentifier" } | Select-Object -First 1
$factoryType = $types | Where-Object { $_.FullName -eq "Launcher.Extensions.Models.AddonIdentifierFactory" } | Select-Object -First 1
$path = "C:\Program Files (x86)\Steam\steamapps\common\DayZ\@MichiganSurvival"

Write-Host "--- LocalAddonIdentifier instance ---"
$obj = $localIdType.GetConstructor(@([string])).Invoke(@($path))
Write-Host ("Type=" + $obj.GetType().FullName)
Write-Host ("ToString=" + $obj.ToString())
foreach ($prop in $localIdType.GetProperties([System.Reflection.BindingFlags]"Public,NonPublic,Instance")) {
    try {
        Write-Host ("PROP " + $prop.Name + "=" + $prop.GetValue($obj, $null))
    } catch {}
}

Write-Host "--- Factory static fields ---"
foreach ($field in $factoryType.GetFields([System.Reflection.BindingFlags]"Public,NonPublic,Static")) {
    Write-Host ("FIELD " + $field.Name + " type " + $field.FieldType.FullName)
    try {
        $value = $field.GetValue($null)
        if ($value -is [System.Collections.IDictionary]) {
            foreach ($key in $value.Keys) {
                Write-Host ("  KEY " + $key + " => " + $value[$key])
            }
        } elseif ($value -is [System.Array]) {
            Write-Host ("  VALUE " + ($value -join ","))
        } else {
            Write-Host ("  VALUE " + $value)
        }
    } catch {
        Write-Host ("  ERR " + $_.Exception.Message)
    }
}

Write-Host "--- Factory parse attempts ---"
$factory = $null
try {
    $factory = [Activator]::CreateInstance($factoryType, $true)
} catch {
    Write-Host ("no instance: " + $_.Exception.Message)
}
$create = $factoryType.GetMethod("Create", [System.Reflection.BindingFlags]"Public,NonPublic,Instance,Static")
$tests = @(
    $path,
    ("local:" + $path),
    ("local|" + $path),
    ("local;" + $path),
    ("local::" + $path),
    ("file:" + $path)
)
foreach ($text in $tests) {
    try {
        $target = if ($create.IsStatic) { $null } else { $factory }
        $result = $create.Invoke($target, @($text))
        Write-Host ("CREATE [" + $text + "] => " + $result.GetType().FullName + " ToString=" + $result.ToString())
    } catch {
        $message = $_.Exception.Message
        if ($_.Exception.InnerException) {
            $message = $_.Exception.InnerException.Message
        }
        Write-Host ("CREATE [" + $text + "] => ERROR " + $message)
    }
}
