# Build Instructions - Secure EXE

## Install Build Dependencies

```bash
# Install PyArmor (obfuscation)
pip install pyarmor

# Install PyInstaller
pip install pyinstaller

# Install other dependencies
pip install -r requirements.txt
```

## Build Commands

### Option 1: Secure Build (Recommended)
```bash
python build_secure.py
```

This will:
1. Clean old build artifacts
2. Obfuscate source code with PyArmor
3. Build EXE with PyInstaller

### Option 2: Normal Build
```bash
pyinstaller MCA_Brain_System_v1.0.spec --noconfirm
```

## Security Features

| Feature | Description |
|---------|-------------|
| **Bytecode Obfuscation** | PyArmor encrypts Python bytecode |
| **Code Flow Obfuscation** | Scrambles control flow |
| **String Encryption** | Encrypts string constants |
| **Anti-Debug** | Detects debugger tampering |
| **UPX Compression** | Compresses EXE size |

## Output

- Location: `dist/MCA_Brain_System_v1.0/`
- EXE: `MCA_Brain_System_v1.0.exe`

## Notes

- First build may take 5-10 minutes
- Obfuscated code is slightly slower but much harder to reverse
- Some antivirus may flag obfuscated EXE - this is normal
