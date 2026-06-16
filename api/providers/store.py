"""Provider 配置的 YAML 文件存储。"""

from pathlib import Path

import yaml

from api.providers import ProviderConfig


class ProviderConfigStore:
    """读写 providers.yaml，API key 直接存储在文件中。"""

    def __init__(self, path: str | Path = "providers.yaml"):
        self.path = Path(path)

    def load_all(self) -> list[ProviderConfig]:
        """返回所有配置（不论 enabled 与否）。"""
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return [ProviderConfig(**item) for item in raw.get("providers", [])]

    def get(self, provider_id: str) -> ProviderConfig | None:
        """按 id 查找配置。"""
        for c in self.load_all():
            if c.id == provider_id:
                return c
        return None

    def save(self, config: ProviderConfig) -> None:
        """新增或更新配置（按 id 匹配）。"""
        all_configs = self.load_all()
        for i, c in enumerate(all_configs):
            if c.id == config.id:
                all_configs[i] = config
                break
        else:
            all_configs.append(config)
        self._write_all(all_configs)

    def delete(self, provider_id: str) -> bool:
        """删除配置。返回是否实际删除了项目。"""
        all_configs = self.load_all()
        filtered = [c for c in all_configs if c.id != provider_id]
        if len(filtered) == len(all_configs):
            return False
        self._write_all(filtered)
        return True

    def _write_all(self, configs: list[ProviderConfig]) -> None:
        data = {"providers": [c.to_dict() for c in configs]}
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    @property
    def is_empty(self) -> bool:
        return not self.path.exists() or not self.load_all()

    def migrate_from_env(self) -> ProviderConfig | None:
        """首次启动时从 .env 读取 DeepSeek 配置写入 YAML（向后兼容）。"""
        import os

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            return None

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model_name = os.getenv("MODEL_NAME", "deepseek-v4-flash")
        context_window_str = os.getenv("MODEL_CONTEXT_WINDOW", "256000")

        config = ProviderConfig(
            id="deepseek-main",
            provider_type="openai",
            label="DeepSeek",
            api_key=api_key,
            base_url=base_url,
            models=[model_name],
            enabled=True,
            context_window=int(context_window_str),
        )
        self.save(config)
        return config
