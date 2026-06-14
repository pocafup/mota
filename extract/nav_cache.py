"""【GA decoder · navigate_to 持久化缓存层】PersistentNavCache —— §S13 拆成本墙。

动机(handoff §S13)：含盾深目标 navigate_to 冷算 26s、一轮 GA pop12×gen8 冷算 646s；内存缓存只在
单次 run 内复用、跨 run/调参重付冷成本。本层把 navigate_to 内存缓存的 (键→结果) 落磁盘、跨 run 读回，
让深目标【全局只冷算一次】。

红线(玩家 2026-06-14 定)：
  · 只加【持久化】一层；复用封板件 ga_navigate._nav_key 当身份键、不另造键；
  · 导航逻辑(GBFS/吸收/规整)、封板四件(decode/navigate_to/fitness/detect_*) 一字不改 —— 本层是
    dict-like 对象，由调用方注入到 navigate_to(cache=)，navigate_to 用 cache.get / cache[k]= 照旧；
  · 持久化开/关 GAResult 必须逐字段相同(缓存不改结果)；
  · 版本失效必须正确(改塔数据或导航相关代码 → 旧缓存作废重建、绝不读旧磁盘返错)。

═══ 接缝处理：navigate_to 的键含 id(zone)(内存地址·跨 run 不稳定) ═══
  navigate_to 键 = (id(zone), max_pops, goal_cell, _nav_key(state))。id(zone) 每进程都变 →
  · 内存层：用【完整键】(含 id(zone))，与现状内存缓存字节一致；
  · 磁盘层：剥掉 key[0]=id(zone)，用 (max_pops, goal_cell, _nav_key) 做磁盘键。zone 身份改由
    version_tag 桶(含塔数据指纹)保证 —— 同桶内 zone 唯一，id(zone) 在磁盘层冗余。

═══ disk_key 跨 run 稳定性(经典坑·焊死) ═══
  _nav_key 含多个 frozenset(_suppressed_events / visited_floors / …)。直接 pickle/hash 含 frozenset
  的对象，其元素字节序依赖 PYTHONHASHSEED → 跨 run 不同 → 暖跑不命中(持久化白搭)。故磁盘键先把
  frozenset/set→sorted、dict→sorted-items(_canonical)，再 json 序列化哈希 → 跨 run 确定。

═══ 失效策略：version_tag = sha256(格式版本 ‖ 塔数据指纹 ‖ 导航代码指纹) ═══
  桶目录 cache/nav/<version_tag>/ —— 版本不匹配=走新桶=旧桶物理隔离、绝无可能被误读(比"值里存版本
  读时校验"更焊死)。三部分任一变 → 新桶 → 旧缓存自然作废：
  · 格式版本 FORMAT_VERSION：序列化/键构造方案本身变了手动 bump(逃生舱)。
  · 塔数据指纹：data/games51/ 下全部 .json 内容哈希(数据改→新桶；同时替代 id(zone) 当稳定 zone 身份)。
  · 导航代码指纹：从 ga_navigate.py 自动算【模块级 import 闭包】(项目内文件·跟模块级 import 不跟
    函数级)的内容哈希 —— 自动纳入全部传递依赖(quotient/search/vzone/seg_*/sim 整套)、自动排除
    quotient 函数级 import 的 beam 与未被 import 的 fitness/ga_loop，换塔/重构永不漏纳(玩家 2026-06-14
    拍板选自动闭包·替代手动列文件易腐化)。玩家游戏层保证导航扣血只有【地形伤+战斗】两种、源码层
    坐实两种实现全在 sim/(combat+simulator) → sim/ 整目录被闭包覆盖 → 两套扣血不漏。
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import os
import pickle
from pathlib import Path

FORMAT_VERSION = 1   # 序列化/键构造方案版本；改了 pickle 结构或 disk_key 算法 → bump

_ROOT = Path(__file__).resolve().parent.parent           # mota/
_NAV_ENTRY = _ROOT / "extract" / "ga_navigate.py"         # 导航代码闭包入口
_DATA_DIR = _ROOT / "data" / "games51"
# ga_navigate.py sys.path：parent.parent(根) + parent(extract) → 模块名解析的搜索根
_SEARCH_PATHS = [_ROOT, _ROOT / "extract"]
DEFAULT_CACHE_ROOT = _ROOT / "cache" / "nav"


# ─── 导航代码 import 闭包(模块级·项目内) ─────────────────────────────────────────
def _module_level_imports(pyfile: Path) -> set:
    """解析一个 .py 的【模块级】import 模块名(顶层 + if/try/with/class 块内，但【排除函数体内】)。
    函数级 import(如 quotient 403行 `from solver.beam`·避循环依赖) 不算依赖 → 不纳闭包。"""
    tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
    names: set = set()

    def walk(node, in_func: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, True)                         # 进函数体 → 其内 import 不算模块级
            elif isinstance(child, ast.Import):
                if not in_func:
                    for alias in child.names:
                        names.add(alias.name)
            elif isinstance(child, ast.ImportFrom):
                if not in_func and child.level == 0 and child.module:
                    names.add(child.module)               # 仅绝对 import(本项目无相对)
            else:
                walk(child, in_func)                      # If/Try/With/ClassDef… 继续下探

    walk(tree, False)
    return names


def _resolve_module(modname: str):
    """模块名 → 项目内 .py 路径；标准库/第三方(不在 _SEARCH_PATHS 下) 返回 None。"""
    parts = modname.split(".")
    for base in _SEARCH_PATHS:
        cand = base.joinpath(*parts).with_suffix(".py")
        if cand.is_file():
            return cand.resolve()
        initp = base.joinpath(*parts, "__init__.py")
        if initp.is_file():
            return initp.resolve()
    return None


def nav_code_files() -> list:
    """从 ga_navigate.py 出发，BFS 模块级 import 闭包，返回【项目内】文件排序列表。
    这是导航代码指纹的输入集 —— 单测固定此集合快照防意外增减(tests/test_nav_cache)。"""
    seen: set = set()
    stack = [_NAV_ENTRY.resolve()]
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        for mod in _module_level_imports(f):
            tgt = _resolve_module(mod)
            if tgt is not None and tgt not in seen:
                stack.append(tgt)
    return sorted(seen)


# ─── 指纹 ────────────────────────────────────────────────────────────────────────
def _hash_files(files) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.resolve().relative_to(_ROOT).as_posix().encode("utf-8"))   # 路径(重命名也算变)
        h.update(b"\0")
        h.update(f.read_bytes())                                               # 内容
        h.update(b"\0")
    return h.hexdigest()


def code_fingerprint() -> str:
    return _hash_files(nav_code_files())


def data_fingerprint() -> str:
    return _hash_files(sorted(_DATA_DIR.rglob("*.json")))


def compute_version_tag(format_version: int = FORMAT_VERSION) -> str:
    raw = f"{format_version}|{data_fingerprint()}|{code_fingerprint()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ─── disk_key 规范化(跨 run 稳定) ─────────────────────────────────────────────────
def _canonical(obj):
    """把对象规范成【顺序确定】的纯 list+基本类型结构：frozenset/set→sorted、dict→sorted items、
    tuple→list。消除 frozenset 迭代序对 PYTHONHASHSEED 的依赖 → json 哈希跨 run 稳定。"""
    if isinstance(obj, (tuple, list)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return ["\x00set", sorted((_canonical(x) for x in obj), key=repr)]
    if isinstance(obj, dict):
        return ["\x00dict",
                sorted(((_canonical(k), _canonical(v)) for k, v in obj.items()), key=repr)]
    return obj


# ─── 持久化缓存(dict-like) ────────────────────────────────────────────────────────
class PersistentNavCache:
    """navigate_to 缓存的持久化后端：dict-like(get 默认 None / __setitem__)，可直接传 navigate_to(cache=)。
    查找顺序：内存(完整键含 id(zone)，同现状) → 磁盘(剥 id(zone)+canonical 键，跨 run) → 返 None(冷算)。
    单进程·原子写(tmp+os.replace)·读坏当 miss·绝不因缓存故障崩(缓存是优化不是正确性)。"""
    _MISS = object()

    def __init__(self, cache_root=None, format_version: int = FORMAT_VERSION):
        self._mem: dict = {}
        self.format_version = format_version
        self.version_tag = compute_version_tag(format_version)
        root = Path(cache_root) if cache_root is not None else DEFAULT_CACHE_ROOT
        self.bucket = root / self.version_tag
        self.bucket.mkdir(parents=True, exist_ok=True)
        self._ctr = itertools.count()
        self.stats = {"mem_hit": 0, "disk_hit": 0, "miss": 0, "write": 0, "corrupt": 0}

    def _disk_key(self, key) -> str:
        canon = _canonical(key[1:])                       # 剥离 key[0]=id(zone)
        blob = json.dumps(canon, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _path(self, key) -> Path:
        return self.bucket / (self._disk_key(key) + ".pkl")

    def get(self, key, default=None):
        v = self._mem.get(key, self._MISS)
        if v is not self._MISS:
            self.stats["mem_hit"] += 1
            return v
        p = self._path(key)
        if p.is_file():
            try:
                with open(p, "rb") as fh:
                    val = pickle.load(fh)
            except Exception:                             # 读坏/截断 → 当 miss、best-effort 删
                self.stats["corrupt"] += 1
                try:
                    p.unlink()
                except OSError:
                    pass
                return default
            self._mem[key] = val
            self.stats["disk_hit"] += 1
            return val
        self.stats["miss"] += 1
        return default

    def __getitem__(self, key):
        v = self.get(key, self._MISS)
        if v is self._MISS:
            raise KeyError(key)
        return v

    def __contains__(self, key):
        return self.get(key, self._MISS) is not self._MISS

    def __setitem__(self, key, value):
        self._mem[key] = value
        p = self._path(key)
        tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}.{next(self._ctr)}")
        try:
            with open(tmp, "wb") as fh:
                pickle.dump(value, fh, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, p)                            # 原子替换(Win/POSIX)
            self.stats["write"] += 1
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def __len__(self):
        return len(self._mem)
