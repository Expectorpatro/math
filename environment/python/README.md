# 全书 Python 环境

本目录使用 UV 管理整个项目的 Python 环境。只维护三份项目文件：

- `.python-version`：固定 Python 解释器版本为 3.12.13；
- `pyproject.toml`：人手维护的直接依赖；
- `uv.lock`：UV 自动生成的精确依赖锁文件。

不要提交 `.venv/`，也不要手工编辑 `uv.lock`。章节和计算实验共用这一环境，不应各自创建 Python 或 Conda 环境。

## 从零恢复

先安装 UV，克隆仓库后进入教材根目录。下面命令会按 `.python-version` 准备 Python3.12.13（如本机没有）并严格按锁文件同步环境：

```bash
uv sync --project environment/python --locked
```

运行 Python 或某个工具时，始终通过 UV。

## 与 renv 的“自动启动”

renv 通过 R 启动时读取 `.Rprofile` 改写 R 的包库路径；UV 则不默认激活 shell，而是在每次 `uv run` 时自动定位、检查并使用本项目的 `.venv`。因此，对脚本、Jupyter 和渲染命令，优先使用 `uv run --project environment/python --locked ...`。`--project`指定全书 Python 项目，同时保留教材根目录为当前工作目录，使计算实验中的相对路径仍从教材根目录解析。

如果确实希望进入项目根目录时把 `.venv` 自动放到 shell 的 `PATH`，可自行安装direnv，并在教材根目录创建 `.envrc`：

```bash
export VIRTUAL_ENV="$PWD/environment/python/.venv"
PATH_add "$VIRTUAL_ENV/bin"
```

然后在该根目录执行一次 `direnv allow`。此方案只适用于 macOS/Linux 的 POSIX shell，并且必须先运行 `uv sync --project environment/python --locked` 使 `.venv` 存在。不使用 direnv 时，手动启动的等价命令是：

```bash
source environment/python/.venv/bin/activate
```

`uv run` 与手动/direnv 激活不要混用为两套依赖管理方式：依赖仍只能通过 `uv add`、`uv remove` 和 `uv lock` 修改。

## 添加、更新与删除依赖

所有命令都从教材根目录运行。新增运行时依赖时使用：

```bash
uv add --project environment/python numpy pandas jupyter
```

UV 会同时修改 `pyproject.toml` 和 `uv.lock`。移除依赖时使用：

```bash
uv remove --project environment/python pandas
```

需要升级已锁定的依赖时，执行：

```bash
uv lock --project environment/python --upgrade
```

## 提交与复现边界

应提交 `.python-version`、`pyproject.toml`、`uv.lock` 与本说明。`.venv/`、Jupyter缓存、构建产物及本机 Python 下载缓存均不提交。
