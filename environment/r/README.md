# 全书 R 环境说明

本目录只存放全书 R 环境的使用说明；实际的 `renv` 项目位于**项目根目录**：

```text
<项目根目录>/
├── .Rprofile
├── renv.lock
└── renv/
    ├── activate.R
    └── settings.json
```

这不是目录遗漏，而是有意的设计。`renv::snapshot()` 默认以当前 `renv` 项目根目录为边界，扫描该目录及其子目录中的 R 依赖。若把项目根设为 `environment/r/`，它无法发现教材章节、`.qmd`、`.Rmd`、Notebook 与计算实验目录中实际使用的包；本机已有的包虽然可能让渲染暂时成功，但新的读者恢复 `renv.lock` 后会缺少这些依赖。因此，根目录必须是唯一的 `renv` 项目根，而 `environment/r/` 保留为便于查找的环境文档目录。

请勿在章节或计算实验目录执行 `renv::init()`，也不要建立第二个 `renv.lock`。

## 首次恢复

1. 安装与 `renv.lock` 中记录版本兼容的 R；当前基线为 R 4.5.2。
2. 克隆仓库后，进入**项目根目录**，不要进入某个章节目录。
3. 启动 R，并运行：

```r
renv::restore(prompt = FALSE)
renv::status()
```

`restore()` 会按照根目录的 `renv.lock` 安装所需 R 包；`status()` 应报告项目与锁文件同步。若首次启动需要引导安装 `renv`，接受引导后重新运行上述两行命令即可。

可用下列命令确认当前会话连接到全书环境：

```r
renv::project()
```

输出应是仓库根目录的绝对路径，而不是 `environment/r` 或某个章节目录。从子目录启动 R 时，先切换到项目根目录，或设置 `BOOK_PROJECT_ROOT` 为项目根目录后再加载根目录 `.Rprofile`。

## 修改 R 依赖

所有操作均从教材根目录启动的 R 会话进行。依赖变化后，应检查状态并更新唯一的锁文件：

```r
# 新增或升级一个包
renv::install("ggplot2")

# 删除不再需要的包
renv::remove("ggplot2")

# 将当前依赖版本写入根目录的唯一锁文件
renv::snapshot(prompt = FALSE)
```

若要更新已安装包，使用 `renv::update()` 后同样运行 `snapshot()`。不要手工编辑 `renv.lock`，也不要为图省事使用 `snapshot(type = "all")`：它会把未被全书代码引用的包也写入锁文件，降低环境的可读性与可恢复性。

`snapshot()` 会在教材根目录及其子目录中发现 R 依赖。根目录 `.renvignore` 只排除本机UV 虚拟环境 `environment/python/.venv/` 与生成的网页输出；它们都不是 R 源代码，而且Python 环境可由 `environment/python/uv.lock` 恢复。若新增体积很大的本机缓存或生成目录，可将其**精确路径**加入 `.renvignore`，但不要忽略章节目录、`computations/`、`.R`、`.Rmd`、`.qmd` 或 Notebook；否则 `snapshot()` 可能漏掉真正使用的 R 包。

## 提交与复现边界

每次依赖变动后应提交：

- 根目录 `renv.lock`；
- 根目录 `renv/activate.R`、`renv/settings.json`、`renv/.gitignore`；
- 根目录 `.renvignore`（依赖扫描的排除边界）；
- 根目录 `.Rprofile`（仅在启动配置变化时）。

不得提交 `renv/library/`：它是每台机器自己的二进制包库。`renv.lock` 锁定 R 包的来源与版本，但不会安装 R 本身、操作系统库或 Quarto。
