"""設定の読み書き

config/settings.yaml（リポジトリ管理）の上に config/local.yaml（設定ページでの変更・git 管理外）を重ねる。
人格は config/persona.local.txt（設定ページで編集・git 管理外）があればそちらを優先する。
"""
import copy
import os
from pathlib import Path

import yaml

BASE_PATH = Path('config/settings.yaml')
LOCAL_PATH = Path('config/local.yaml')
LOCAL_PERSONA_PATH = Path('config/persona.local.txt')


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def load_config() -> dict:
    return _merge(_read_yaml(BASE_PATH), _read_yaml(LOCAL_PATH))


def save_local(updates: dict) -> None:
    """updates を config/local.yaml に重ねて保存する"""
    merged = _merge(_read_yaml(LOCAL_PATH), updates)
    _write_atomic(LOCAL_PATH, yaml.safe_dump(merged, allow_unicode=True, sort_keys=False))


def user_location(cfg: dict) -> str:
    """設定ページ（local.yaml）> .env の FURBY_LOCATION > settings.yaml の順"""
    return cfg.get('user', {}).get('location') or os.environ.get('FURBY_LOCATION', '')


def load_persona(cfg: dict) -> str:
    path = LOCAL_PERSONA_PATH if LOCAL_PERSONA_PATH.exists() else Path(cfg['paths']['persona'])
    return path.read_text(encoding='utf-8').strip()


def persona_is_custom() -> bool:
    return LOCAL_PERSONA_PATH.exists()


def save_persona(text: str) -> None:
    _write_atomic(LOCAL_PERSONA_PATH, text.strip() + '\n')


def reset_persona() -> None:
    """設定ページでの編集を捨てて config/persona.txt に戻す"""
    LOCAL_PERSONA_PATH.unlink(missing_ok=True)
