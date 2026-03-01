from __future__ import annotations
import os
from typing import Optional
from config.constants import MAX_LOG_LINE_LENGTH


class InputSanitizer:
    @staticmethod
    def sanitize_log_content(content: str) -> str:
        lines = content.splitlines()
        safe_lines = [line[:MAX_LOG_LINE_LENGTH] for line in lines]
        return "\n".join(safe_lines)

    @staticmethod
    def validate_file_path(path: str, base_dir: Optional[str] = None) -> bool:
        """
        使用增强的安全性（防止目录遍历）验证文件路径。
        :param path: 要验证的文件路径
        :param base_dir: 可选的基础目录，文件必须位于该目录内
        """
        if not path:
            return False
        try:
            # 规范化路径以解析 .. 和符号链接
            norm_path = os.path.abspath(os.path.normpath(path))
            
            # 如果提供了 base_dir，则进行目录遍历检查
            if base_dir:
                abs_base = os.path.abspath(base_dir)
                if not norm_path.startswith(abs_base):
                    return False

            return os.path.exists(norm_path) and os.path.isfile(norm_path)
        except Exception:
            return False

    @staticmethod
    def validate_dir_path(path: str, base_dir: Optional[str] = None, create: bool = False) -> bool:
        """
        验证目录路径安全性。
        :param create: 如果为True且目录不存在，验证其父目录是否安全（不实际创建）
        """
        if not path:
            return False
        try:
            norm_path = os.path.abspath(os.path.normpath(path))
            if base_dir:
                abs_base = os.path.abspath(base_dir)
                if not norm_path.startswith(abs_base):
                    return False
            
            if create:
                # 检查父目录是否存在且是一个目录
                parent = os.path.dirname(norm_path)
                return os.path.exists(parent) and os.path.isdir(parent)
            
            return os.path.exists(norm_path) and os.path.isdir(norm_path)
        except Exception:
            return False
    
    @staticmethod
    def sanitize_url(url: str) -> str | None:
        """在浏览器打开前清洗 URL。"""
        if not url: return None
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            # 仅允许 http/https 方案
            if parsed.scheme not in ('http', 'https'):
                return None
            return url
        except Exception:
            return None


class MemoryLimitExceededError(Exception):
    pass


class CpuLimitExceededError(Exception):
    pass


class ResourceLimiter:
    def __init__(self, max_memory_mb: int = 512, max_cpu_percent: int = 80):
        self.max_memory = max_memory_mb * 1024 * 1024
        self.max_cpu = max_cpu_percent
        self._process = None
        self._init_cpu_monitor()
    
    def _init_cpu_monitor(self):
        """初始化CPU监控，需要预先调用一次建立基准"""
        try:
            import psutil
            self._process = psutil.Process()
            # 第一次调用建立基准值，返回0是正常的
            self._process.cpu_percent(interval=None)
        except Exception:
            self._process = None

    def _get_memory_usage(self) -> int:
        """获取当前进程的内存使用量（字节）"""
        try:
            import psutil
            return psutil.Process().memory_info().rss
        except Exception:
            return 0

    def _get_cpu_usage(self) -> int:
        """获取当前进程的CPU使用率（百分比）
        
        注意：第一次调用后需要间隔一段时间再调用才能获得有意义的值。
        如果调用太频繁，返回的结果可能不准确。
        """
        if self._process is None:
            return 0
        try:
            # interval=None 表示非阻塞，返回自上次调用以来的CPU使用率
            return int(self._process.cpu_percent(interval=None))
        except Exception:
            return 0

    def check_limits(self):
        """检查资源限制，如果超过限制则抛出异常"""
        if self._get_memory_usage() > self.max_memory:
            raise MemoryLimitExceededError()
        if self._get_cpu_usage() > self.max_cpu:
            raise CpuLimitExceededError()



class ErrorSanitizer:
    """错误信息脱敏，防止泄露用户敏感路径"""
    
    @staticmethod
    def sanitize_error_message(message: str) -> str:
        """移除错误信息中的敏感路径信息"""
        if not message:
            return "未知错误"
        
        import re
        import os
        
        # 移除用户目录路径
        home = os.path.expanduser("~")
        if home:
            message = message.replace(home, "~")
        
        # 移除盘符路径模式（如 C:\\Users\\...）
        message = re.sub(r'[A-Za-z]:\\[^\s]+', '[路径]', message)
        
        # 移除 /home/ 用户路径
        message = re.sub(r'/home/[^/]+', '/home/[用户]', message)
        
        # 移除临时目录
        temp = os.environ.get('TEMP') or os.environ.get('TMP')
        if temp:
            message = message.replace(temp, '[临时目录]')
        
        # 移除 Python 内部路径
        message = re.sub(r'File "[^"]+\\.py",', 'File "[文件]",', message)
        
        return message
    
    @staticmethod
    def sanitize_traceback(tb: str) -> str:
        """清理堆栈跟踪中的敏感路径"""
        if not tb:
            return ""
        
        import re
        import os
        
        lines = tb.split('\n')
        cleaned = []
        
        for line in lines:
            line = re.sub(r'File "([^"]+)\.py",', lambda m: 
                'File "' + os.path.basename(m.group(1)) + '.py",', line)
            
            home = os.path.expanduser("~")
            if home:
                line = line.replace(home, "~")
            
            cleaned.append(line)
        
        return '\n'.join(cleaned)


class DebugDetector:
    """调试器/开发者工具检测"""
    
    @staticmethod
    def is_debugging() -> bool:
        """检测是否在调试器中运行"""
        import sys
        
        if getattr(sys, 'gettrace', lambda: None)():
            return True
        
        ide_indicators = ['pydevd', 'debugpy', 'ipdb', 'pdb', 'wing', 'komodo']
        
        for indicator in ide_indicators:
            if indicator in sys.modules:
                return True
        
        return False
    
    @staticmethod
    def is_virtual_machine() -> bool:
        """检测是否在虚拟机中运行"""
        import os
        
        vm_files = [
            '/proc/scsi/scsi',
            '/proc/cpuinfo',
            'C:\\Windows\\System32\\drivers\\vmmouse',
        ]
        
        for f in vm_files:
            if os.path.exists(f):
                return True
        
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'hypervisor' in f.read():
                    return True
        except:
            pass
        
        return False


class IntegrityChecker:
    """文件完整性校验，防止关键文件被篡改"""
    
    def __init__(self, base_dir: str = None):
        import os
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._hash_cache: dict = {}
        
    def compute_file_hash(self, filepath: str) -> str:
        """计算文件的 SHA256 哈希"""
        import hashlib
        
        try:
            with open(filepath, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def verify_integrity(self, known_hashes: dict = None) -> tuple:
        """验证关键文件完整性"""
        import os
        
        critical_files = [
            'src/mca_core/security.py',
            'src/config/constants.py',
            'src/mca_core/launcher.py',
        ]
        
        modified = []
        
        for rel_path in critical_files:
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                current_hash = self.compute_file_hash(full_path)
                
                if known_hashes and rel_path in known_hashes:
                    if current_hash != known_hashes[rel_path]:
                        modified.append(rel_path)
        
        return (len(modified) == 0, modified)
    
    def get_current_hashes(self) -> dict:
        """获取当前关键文件的哈希值"""
        import os
        
        hashes = {}
        critical_files = [
            'src/mca_core/security.py',
            'src/config/constants.py',
            'src/mca_core/launcher.py',
        ]
        
        for rel_path in critical_files:
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                hashes[rel_path] = self.compute_file_hash(full_path)
        
        return hashes
    
    def save_baseline(self, filepath: str = None) -> bool:
        """
        保存当前哈希基线到本地文件（离线模式使用）
        
        Args:
            filepath: 保存路径，默认在 data/ 目录
            
        Returns:
            是否保存成功
        """
        import os
        import json
        
        if filepath is None:
            data_dir = os.path.join(self.base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "integrity_baseline.json")
        
        try:
            hashes = self.get_current_hashes()
            baseline = {
                "version": "1.0",
                "created_at": str(os.path.getmtime(__file__)),
                "files": hashes
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(baseline, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def load_baseline(self, filepath: str = None) -> dict:
        """
        加载本地哈希基线
        
        Returns:
            基线哈希字典，失败返回空字典
        """
        import os
        import json
        
        if filepath is None:
            data_dir = os.path.join(self.base_dir, "data")
            filepath = os.path.join(data_dir, "integrity_baseline.json")
        
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("files", {})
        except:
            pass
        return {}
    
    def verify_offline(self) -> tuple:
        """
        离线模式校验（不联网）
        
        Returns:
            (is_valid, modified_files, message)
        """
        import os
        
        baseline = self.load_baseline()
        
        if not baseline:
            # 没有基线，提示用户创建
            return (None, [], "无基线，请运行 --create-baseline 创建")
        
        return self.verify_integrity(baseline)
    
    def export_offline_fix_package(self, output_dir: str) -> str:
        """
        导出离线修复包（打包发布时使用）
        
        将当前正确版本的关键文件打包，供断网用户手动修复
        
        Args:
            output_dir: 输出目录
            
        Returns:
            修复包路径
        """
        import os
        import zipfile
        import json
        import shutil
        
        os.makedirs(output_dir, exist_ok=True)
        
        critical_files = [
            'src/mca_core/security.py',
            'src/config/constants.py',
            'src/mca_core/launcher.py',
        ]
        
        # 创建临时目录
        temp_dir = os.path.join(output_dir, "_temp_fix")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        # 复制文件
        for rel_path in critical_files:
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                dest = os.path.join(temp_dir, rel_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full_path, dest)
        
        # 保存哈希基线
        hashes = self.get_current_hashes()
        with open(os.path.join(temp_dir, "baseline.json"), 'w', encoding='utf-8') as f:
            json.dump({"files": hashes, "version": "1.0"}, f, indent=2)
        
        # 创建 zip
        zip_path = os.path.join(output_dir, "integrity_fix.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_dir)
                    zf.write(full_path, arcname)
        
        # 清理
        shutil.rmtree(temp_dir)
        
        return zip_path


class GitHubAutoRepair:
    """GitHub 实时联网，自动修复被篡改的核心文件"""
    
    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        branch: str = "main",
        token: str = None
    ):
        """
        初始化 GitHub 自动修复
        
        Args:
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            branch: 分支名
            token: GitHub Personal Access Token (可选，提高 API 限制)
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.token = token
        self.base_url = "https://api.github.com"
        
    def _get_headers(self) -> dict:
        """获取 API 请求头"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    def fetch_file_content(self, file_path: str) -> tuple[bool, str]:
        """
        从 GitHub 获取文件内容
        
        Returns:
            (success, content_or_error_message)
        """
        import urllib.request
        import json
        
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}?ref={self.branch}"
        
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                if "content" in data:
                    import base64
                    content = base64.b64decode(data["content"]).decode("utf-8")
                    return (True, content)
                else:
                    return (False, "文件不存在或无法访问")
                    
        except urllib.error.HTTPError as e:
            return (False, f"HTTP错误: {e.code}")
        except Exception as e:
            return (False, f"网络错误: {str(e)}")
    
    def verify_and_repair(
        self,
        file_path: str,
        local_base_dir: str,
        backup: bool = True
    ) -> tuple[bool, str]:
        """
        验证并自动修复文件
        
        Args:
            file_path: 文件在仓库中的路径 (如 "src/mca_core/security.py")
            local_base_dir: 本地项目根目录
            backup: 是否在修复前备份原文件
            
        Returns:
            (success, message)
        """
        import os
        import shutil
        import hashlib
        
        local_path = os.path.join(local_base_dir, file_path)
        
        # 获取 GitHub 最新版本
        success, remote_content = self.fetch_file_content(file_path)
        if not success:
            return (False, f"无法获取远程文件: {remote_content}")
        
        # 计算远程哈希
        remote_hash = hashlib.sha256(remote_content.encode()).hexdigest()
        
        # 检查本地文件
        if not os.path.exists(local_path):
            # 文件不存在，直接创建
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(remote_content)
            return (True, f"文件不存在，已从 GitHub 下载")
        
        # 计算本地哈希
        with open(local_path, 'rb') as f:
            local_hash = hashlib.sha256(f.read()).hexdigest()
        
        # 比较哈希
        if local_hash == remote_hash:
            return (True, "文件完整，无需修复")
        
        # 文件被篡改，进行修复
        if backup:
            backup_path = local_path + ".corrupted"
            shutil.copy2(local_path, backup_path)
        
        # 写入正确内容
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(remote_content)
        
        return (True, f"文件已损坏，已从 GitHub 修复 (原文件备份为 {os.path.basename(backup_path) if backup else 'N/A'})")
    
    def batch_repair(
        self,
        files: list[str],
        local_base_dir: str
    ) -> dict:
        """
        批量验证并修复文件
        
        Returns:
            {file_path: (success, message)}
        """
        results = {}
        for file_path in files:
            success, message = self.verify_and_repair(file_path, local_base_dir)
            results[file_path] = (success, message)
        return results


# 便捷函数：快速初始化（需要配置）
def get_default_repair() -> GitHubAutoRepair | None:
    """获取默认的自动修复实例（在 config 中配置）"""
    import os
    
    # 从环境变量或配置文件读取
    token = os.environ.get("GITHUB_TOKEN")
    
    # 尝试从配置文件读取
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "repair_config.json")
    if os.path.exists(config_path):
        import json
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                repo_owner = config.get("repo_owner", "")
                repo_name = config.get("repo_name", "")
                if not repo_owner or not repo_name:
                    return None
                # V-006 Fix: Use token_env field to read token from environment variable
                token_env_name = config.get("token_env", "GITHUB_TOKEN")
                token = os.environ.get(token_env_name) or None
                return GitHubAutoRepair(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    branch=config.get("branch", "main"),
                    token=token
                )
        except:
            pass
    
    return None



class ExternalLibValidator:
    """外部库安全校验 - 防止恶意代码注入"""
    
    # 可信模块白名单
    TRUSTED_MODULES = {
        'os', 'sys', 'json', 'logging', 'threading', 'time', 'datetime',
        'collections', 're', 'math', 'random', 'hashlib', 'base64', 'zipfile',
        'urllib', 'http', 'html', 'xml', 'csv', 'io', 'copy',
        'tkinter', 'PIL', 'matplotlib', 'networkx', 'numpy',
        'mca_core', 'brain_system', 'config', 'utils', 'dlcs',
    }
    
    # 危险模块黑名单
    DANGEROUS_MODULES = {'ctypes', 'code', 'codeop', 'pty', 'tty', 'termios'}
    
    @classmethod
    def validate_module(cls, module_name: str) -> tuple:
        """验证模块是否允许加载"""
        import os
        import importlib.util
        
        base_module = module_name.split('.')[0]
        
        if base_module in cls.TRUSTED_MODULES:
            return (True, "白名单允许")
        
        if base_module in cls.DANGEROUS_MODULES:
            return (False, f"危险模块: {base_module}")
        
        # 检查模块路径
        try:
            spec = importlib.util.find_spec(base_module)
            if spec and spec.origin:
                import pathlib
                stdlib = pathlib.Path(os.__file__).parent
                sitepkgs = stdlib / 'site-packages'
                if spec.origin.startswith(str(stdlib)) or spec.origin.startswith(str(sitepkgs)):
                    return (True, "标准库/site-packages")
                return (False, f"未知路径: {spec.origin}")
        except:
            pass
        
        return (True, "默认允许")
    
    @classmethod
    def validate_lib_directory(cls, lib_dir: str) -> tuple:
        """验证 lib 目录中的所有模块"""
        import os
        
        warnings = []
        
        if not os.path.exists(lib_dir):
            return (True, ["lib 目录不存在"])
        
        for root, dirs, files in os.walk(lib_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    rel_path = os.path.relpath(os.path.join(root, file), lib_dir)
                    module_name = rel_path.replace('\\', '.').replace('/', '.')[:-3]
                    
                    is_allowed, reason = cls.validate_module(module_name)
                    if not is_allowed:
                        warnings.append(f"{module_name}: {reason}")
        
        return (len(warnings) == 0, warnings)

