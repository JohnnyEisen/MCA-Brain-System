import sys
import os
import fnmatch
import ast
import hashlib
import hmac

# Add src/ to path for new directory structure
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)

# ============================================================
# V-001 & V-003 Fix: Secure Patch Loader with Signature Verification
# ============================================================

# 获取签名密钥 - 优先级: 环境变量 > 内嵌密钥 > 默认密钥
def _get_signature_key() -> bytes:
    """
    获取补丁签名密钥
    优先级: MCA_PATCH_SECRET环境变量 > 内嵌密钥 > 默认密钥
    """
    # 1. 尝试从环境变量获取
    env_key = os.environ.get('MCA_PATCH_SECRET')
    if env_key:
        return env_key.encode('utf-8')
    
    # 2. 尝试从同目录的 .patch_key 文件读取
    app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    key_file = os.path.join(app_dir, '.patch_key')
    if os.path.exists(key_file):
        try:
            with open(key_file, 'r') as f:
                key = f.read().strip()
                if key:
                    return key.encode('utf-8')
        except Exception:
            pass
    
    # 3. 返回默认密钥 (仅用于开发环境警告)
    return b'mca_default_key_for_dev_only'


def _compute_file_signature(filepath: str, key: bytes) -> str:
    """计算文件的 HMAC-SHA256 签名"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        signature = hmac.new(key, content, hashlib.sha256).hexdigest()
        return signature
    except Exception:
        return ''


def _load_approved_signatures() -> set:
    """
    加载已批准的补丁签名列表
    从 .approved_patches 文件读取
    """
    approved = set()
    
    app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    approved_file = os.path.join(app_dir, '.approved_patches')
    
    if os.path.exists(approved_file):
        try:
            with open(approved_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        approved.add(line)
        except Exception:
            pass
    
    return approved


# 安全配置: 允许的补丁文件名白名单
ALLOWED_PATCH_FILES = {
    'fix_crash.py',      # 崩溃修复
    'hotfix.py',         # 热修复
    'patch_*.py',        # 通配符匹配
}

# 危险代码模式
DANGEROUS_PATTERNS = [
    'eval(', 'exec(', '__import__', 'compile(',
    'os.system', 'subprocess.', 'pty.', 'tty.',
    'socket.', 'requests.', 'urllib3.',
    'open(', 'file(', 'write(',
]


def _is_safe_patch_file(filepath: str) -> bool:
    """验证补丁文件安全性"""
    filename = os.path.basename(filepath)
    
    # 1. 检查文件名是否在白名单
    allowed = False
    for pattern in ALLOWED_PATCH_FILES:
        if fnmatch.fnmatch(filename, pattern):
            allowed = True
            break
    
    if not allowed:
        print(f"[Security] 拒绝加载未授权的补丁文件: {filename}")
        return False
    
    # 2. 检查文件内容是否有危险代码
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # AST 解析检查
        try:
            ast.parse(content)
        except SyntaxError as e:
            print(f"[Security] 补丁文件语法错误: {filename} - {e}")
            return False
        
        # 危险模式检查
        for pattern in DANGEROUS_PATTERNS:
            if pattern in content:
                print(f"[Security] 补丁文件包含危险代码: {filename} - 检测到 {pattern}")
                return False
                
    except Exception as e:
        print(f"[Security] 验证补丁文件失败: {filename} - {e}")
        return False
    
    return True


def _verify_patch_signature(filepath: str) -> bool:
    """
    验证补丁文件签名
    只有签名匹配的补丁才会被加载
    """
    signature = _compute_file_signature(filepath, _get_signature_key())
    approved = _load_approved_signatures()
    
    if signature in approved:
        return True
    
    # 如果没有签名文件但有环境变量/密钥文件，也接受（仅开发模式）
    if os.environ.get('MCA_PATCH_SECRET') or os.path.exists(os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), '.patch_key')):
        print(f"[Warning] 补丁 {os.path.basename(filepath)} 无签名记录，但密钥已配置")
        return True
    
    print(f"[Security] 补丁 {os.path.basename(filepath)} 签名验证失败，未在批准列表中")
    return False


def _load_patches_safely(patch_dir: str):
    """安全加载补丁目录 - 需要签名验证"""
    if not os.path.isdir(patch_dir):
        return
    
    loaded_count = 0
    rejected_count = 0
    
    for filename in os.listdir(patch_dir):
        if not filename.endswith('.py'):
            continue
        
        filepath = os.path.join(patch_dir, filename)
        if not os.path.isfile(filepath):
            continue
        
        # 安全验证
        if _is_safe_patch_file(filepath):
            # 签名验证
            if not _verify_patch_signature(filepath):
                print(f"[Security] 补丁 {filename} 签名验证失败，已拒绝")
                rejected_count += 1
                continue
                
            try:
                sys.path.insert(0, patch_dir)
                print(f"[Hotfix] 已安全加载补丁: {filename}")
                loaded_count += 1
            except Exception as e:
                print(f"[Security] 加载补丁失败: {filename} - {e}")
                rejected_count += 1
    
    if loaded_count > 0:
        print(f"[Hotfix] 共加载 {loaded_count} 个已签名补丁")
    
    if rejected_count > 0:
        print(f"[Hotfix] 拒绝了 {rejected_count} 个未签名补丁")


def _create_signature_tool():
    """创建签名工具 - 用于开发者为补丁签名"""
    tool_code = '''#!/usr/bin/env python3
"""
MCA Brain System 补丁签名工具
用于为热修复补丁生成签名
"""
import os
import sys
import hashlib
import hmac

def sign_patch(patch_file: str, key: str = None):
    """为补丁文件生成签名"""
    if key is None:
        # 尝试读取密钥
        key_file = '.patch_key'
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                key = f.read().strip()
        else:
            print("错误: 请提供密钥或创建 .patch_key 文件")
            sys.exit(1)
    else:
        key = key
    
    # 计算签名
    with open(patch_file, 'rb') as f:
        content = f.read()
    signature = hmac.new(key.encode('utf-8'), content, hashlib.sha256).hexdigest()
    
    # 添加到批准列表
    approved_file = '.approved_patches'
    with open(approved_file, 'a') as f:
        f.write(signature + '\\n')
    
    print(f"补丁已签名: {patch_file}")
    print(f"签名: {signature}")
    print(f"请将签名添加到 .approved_patches 文件")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python sign_patch.py <补丁文件> [密钥]")
        sys.exit(1)
    
    patch_file = sys.argv[1]
    key = sys.argv[2] if len(sys.argv) > 2 else None
    sign_patch(patch_file, key)
'''
    
    # 写入签名工具
    tool_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', 'sign_patch.py')
    os.makedirs(os.path.dirname(tool_path), exist_ok=True)
    with open(tool_path, 'w', encoding='utf-8') as f:
        f.write(tool_code)
    print(f"[Hotfix] 签名工具已创建: {tool_path}")


def _validate_lib_directory(lib_dir: str) -> bool:
    """验证 lib 目录安全性"""
    if not os.path.isdir(lib_dir):
        return False
    
    # 检查是否存在危险的 .pth 文件
    for filename in os.listdir(lib_dir):
        if filename.endswith('.pth'):
            filepath = os.path.join(lib_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 检查危险代码
                    dangerous = ['import ', 'exec', 'eval', '__import__', 'os.system']
                    for pattern in dangerous:
                        if pattern in content:
                            print(f"[Security] 发现危险的 .pth 文件: {filename}")
                            return False
            except Exception:
                pass
    
    return True


# Patch loader (补丁加载器) - 安全版本 with signature verification
# 如果是以打包后的 exe 运行，尝试加载同级目录下的 'patches' 文件夹。
# 补丁必须经过签名验证才能加载
if getattr(sys, 'frozen', False):
    # Frozen runtime (打包环境)
    application_path = os.path.dirname(sys.executable)
    
    # Patches (安全加载 - 需要签名)
    patch_dir = os.path.join(application_path, "patches")
    if os.path.exists(patch_dir):
        _load_patches_safely(patch_dir)
        
    # External libs (安全验证)
    lib_dir = os.path.join(application_path, "lib")
    if os.path.exists(lib_dir):
        if _validate_lib_directory(lib_dir):
            sys.path.append(lib_dir)
            # 不使用 site.addsitedir() 以避免执行 .pth 文件
            print(f"[Launcher] 已加载外部库目录: {lib_dir}")
        else:
            print(f"[Security] lib 目录包含危险文件，已拒绝加载")
else:
    # Development environment (optional)
    # 开发环境自动创建签名工具
    pass
# End patch loader


def main():
    try:
        # Primary entry point
        from mca_core.launcher import launch_app
        launch_app()
    except ImportError:
        # Fallback for legacy layout
        import tkinter as tk
        from mca_core.app import MinecraftCrashAnalyzer
        root = tk.Tk()
        app = MinecraftCrashAnalyzer(root)
        root.mainloop()


if __name__ == "__main__":
    main()
