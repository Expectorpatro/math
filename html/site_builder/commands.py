"""External command execution with consistent diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Mapping, Sequence

from .errors import BuildError


@dataclass(slots=True)
class CommandRunner:
    """Run project tools without mutating the user's process environment."""

    prefix: str = "[web]"

    def log(self, message: str) -> None:
        print(f"{self.prefix} {message}")

    def warning(self, message: str) -> None:
        print(f"{self.prefix} 警告：{message}", file=os.sys.stderr)

    def require(
        self, executable: str | Path, purpose: str | None = None
    ) -> str:
        configured = str(executable)
        found = shutil.which(configured)
        if found is None:
            suffix = f"（用于{purpose}）" if purpose else ""
            raise BuildError(f"找不到所需工具 {configured}{suffix}")
        return found

    def run(
        self,
        command: Sequence[str | Path],
        *,
        cwd: Path,
        input_text: str | None = None,
        environment: Mapping[str, str] | None = None,
        quiet: bool = False,
    ) -> str:
        arguments = [str(item) for item in command]
        process_environment = os.environ.copy()
        if environment:
            process_environment.update(environment)
        result = subprocess.run(
            arguments,
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            env=process_environment,
        )
        if result.stderr.strip() and not quiet:
            print(result.stderr.rstrip(), file=os.sys.stderr)
        if result.returncode != 0:
            rendered = " ".join(shlex.quote(value) for value in arguments)
            details = result.stderr.strip() or result.stdout.strip()
            if len(details) > 4000:
                details = details[-4000:]
            message = f"命令执行失败（退出码 {result.returncode}）：{rendered}"
            if details:
                message += f"\n{details}"
            raise BuildError(message)
        return result.stdout
