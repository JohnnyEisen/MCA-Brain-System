#!/usr/bin/env python3
"""
MCA Brain System 补丁签名工具

用于为热修复补丁生成签名

使用方法:
1. 创建签名密钥:
   echo "your-secret-key" > .patch_key
   
2. 为补丁签名:
   python tools/sign_patch.py patches/fix_crash.py
   
3. 签名会自动添加到 .approved_patches 文件
"""
from typing import Optional
import os
import sys
import hashlib
import hmac


def sign_patch(patch_file: str, key: Optional[str] = None) -> None:
    """为补丁文件生成签名"""
    # 获取密钥
    if key is None:
        # 尝试读取密钥文件
        key_file = '.patch_key'
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                key = f.read().strip()
        else:
            print("错误: 请提供密钥或创建 .patch_key 文件")
            print("用法: python sign_patch.py <补丁文件> [密钥]")
            sys.exit(1)
    
    # 检查补丁文件是否存在
    if not os.path.exists(patch_file):
        print(f"错误: 补丁文件不存在: {patch_file}")
        sys.exit(1)
    
    # 此时 key 必须是 str
    if key is None:
        print("错误: 密钥获取失败")
        sys.exit(1)
    
    # 计算签名
    with open(patch_file, 'rb') as f:
        content = f.read()
    signature = hmac.new(key.encode('utf-8'), content, hashlib.sha256).hexdigest()
    
    # 添加到批准列表
    approved_file = '.approved_patches'
    with open(approved_file, 'a') as f:
        f.write(signature + '\n')
    
    print(f"✓ 补丁已签名: {patch_file}")
    print(f"✓ 签名: {signature}")
    print(f"\n请将以下内容添加到打包目录:")
    print(f"  - .approved_patches 文件")
    print(f"  - .patch_key 文件 (可选)")


def main() -> None:
    if len(sys.argv) < 2:
        print("MCA Brain System 补丁签名工具")
        print("=" * 40)
        print("用法: python sign_patch.py <补丁文件> [密钥]")
        print()
        print("示例:")
        print('  echo "my-secret-key" > .patch_key')
        print('  python tools/sign_patch.py patches/fix_crash.py')
        sys.exit(1)
    
    patch_file = sys.argv[1]
    key = sys.argv[2] if len(sys.argv) > 2 else None
    sign_patch(patch_file, key)


if __name__ == '__main__':
    main()
