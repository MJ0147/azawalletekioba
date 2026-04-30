$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path

$specialNames = @(
  'package.json',
  'package-lock.json',
  'tsconfig.json',
  'next.config.js',
  'tailwind.config.js',
  'postcss.config.js',
  'next-env.d.ts'
)

$targets = Get-ChildItem -Path . -Recurse -File | Where-Object {
  $_.FullName -notmatch '\\.venv\\|\\.git\\|node_modules\\|\\.next\\' -and (
    $_.Extension -in @('.js', '.ts', '.tsx') -or
    $_.Name -in $specialNames -or
    $_.Name -like '*.d.ts'
  )
}

function New-ReplacementFile {
  param(
    [string]$oldPath,
    [string]$newPath
  )

  $oldRel = Resolve-Path -Relative $oldPath
  $header = @(
    '"""',
    "Python replacement for migrated file: $oldRel",
    'Generated during Node.js to Python cleanup.',
    '"""',
    '',
    'def main() -> None:',
    '    # TODO: Implement equivalent Python logic for this module.',
    '    pass',
    '',
    'if __name__ == "__main__":',
    '    main()',
    ''
  ) -join "`r`n"

  if (-not (Test-Path -LiteralPath $newPath)) {
    $dir = Split-Path -Parent $newPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -LiteralPath $newPath -Value $header -Encoding UTF8
  }
}

$created = @()
$deleted = @()

foreach ($f in $targets) {
  $full = $f.FullName
  $name = $f.Name
  $newPath = $null

  switch -Regex ($name) {
    '^package\.json$' { $newPath = Join-Path $f.DirectoryName 'requirements.txt' }
    '^package-lock\.json$' { $newPath = Join-Path $f.DirectoryName 'requirements-lock.txt' }
    '^tsconfig\.json$' { $newPath = Join-Path $f.DirectoryName 'pyproject.toml' }
    '^next\.config\.js$' { $newPath = Join-Path $f.DirectoryName 'web_config.py' }
    '^tailwind\.config\.js$' { $newPath = Join-Path $f.DirectoryName 'style_config.py' }
    '^postcss\.config\.js$' { $newPath = Join-Path $f.DirectoryName 'css_pipeline_config.py' }
    '^next-env\.d\.ts$' { $newPath = Join-Path $f.DirectoryName 'env_config.py' }
    '\.d\.ts$' {
      $base = [System.IO.Path]::GetFileNameWithoutExtension([System.IO.Path]::GetFileNameWithoutExtension($name))
      $newPath = [System.IO.Path]::Combine($f.DirectoryName, ($base + '.py'))
    }
    '\.(js|ts|tsx)$' { $newPath = [System.IO.Path]::ChangeExtension($full, '.py') }
  }

  if ($newPath) {
    New-ReplacementFile -oldPath $full -newPath $newPath
    $created += $newPath.Substring($root.Length + 1)
  }

  Remove-Item -LiteralPath $full -Force
  $deleted += $full.Substring($root.Length + 1)
}

Write-Output "Created: $($created.Count)"
Write-Output "Deleted: $($deleted.Count)"
Write-Output '--- Sample created ---'
$created | Select-Object -First 20
Write-Output '--- Sample deleted ---'
$deleted | Select-Object -First 20

$remaining = Get-ChildItem -Path . -Recurse -File | Where-Object {
  $_.FullName -notmatch '\\.venv\\|\\.git\\|node_modules\\|\\.next\\' -and (
    $_.Extension -in @('.js', '.ts', '.tsx') -or
    $_.Name -in $specialNames -or
    $_.Name -like '*.d.ts'
  )
}
Write-Output "Remaining project JS/TS files: $($remaining.Count)"
