"""
src.pipeline — 7 阶段文档流水线
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .template import TemplateRenderer

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


# ────────────────── 数据类 ──────────────────

@dataclass
class StageResult:
    stage: str
    duration_ms: int
    ok: bool = True
    error: Optional[str] = None
    output_summary: Optional[str] = None


@dataclass
class PipelineResult:
    template: str
    rendered: str
    fingerprint: str
    archive_path: Optional[str] = None
    stages: list[StageResult] = field(default_factory=list)
    distribute_result: Any = None
    audit_id: Optional[str] = None


# ────────────────── 各阶段 ──────────────────

class Ingestor:
    """加载原始数据。支持 dict / json string / file path."""

    def ingest(self, source: Any) -> dict:
        if isinstance(source, dict):
            return dict(source)
        if isinstance(source, str):
            # 看是路径还是 json
            p = Path(source)
            if p.exists():
                ext = p.suffix.lower()
                if ext in (".json",):
                    return json.loads(p.read_text(encoding="utf-8"))
                if ext in (".csv",):
                    rows = list(csv.DictReader(p.open(encoding="utf-8")))
                    return {"rows": rows}
                if ext in (".yaml", ".yml"):
                    try:
                        import yaml
                    except ImportError as e:
                        raise RuntimeError(
                            "PyYAML required for YAML ingest"
                        ) from e
                    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                # plain text
                return {"text": p.read_text(encoding="utf-8")}
            # 不是路径，按 json 字符串
            try:
                return json.loads(source)
            except json.JSONDecodeError:
                return {"text": source}
        raise TypeError(f"Cannot ingest {type(source).__name__}")


class Normalizer:
    """字段标准化 / 默认值填充."""

    DEFAULTS = {
        "generated_at": lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
    }

    def normalize(self, data: dict, defaults: Optional[dict] = None) -> dict:
        out = dict(data)
        for k, v in (defaults or {}).items():
            out.setdefault(k, v)
        for k, supplier in self.DEFAULTS.items():
            out.setdefault(k, supplier())
        return out


class Extractor:
    """从规整后的数据抽取模板需要的关键指标。"""

    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or {}

    def extract(self, data: dict) -> dict:
        # 默认实现：原样透传 + 派生几个常见字段
        derived = dict(data)

        # rows 数据 → 自动算 total/top
        rows = data.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            derived["row_count"] = len(rows)
            # 找数值列
            numeric_cols = [
                k for k, v in rows[0].items()
                if isinstance(v, (int, float)) or (
                    isinstance(v, str) and v.replace(".", "", 1).isdigit()
                )
            ]
            for col in numeric_cols:
                vals = []
                for r in rows:
                    try:
                        vals.append(float(r.get(col, 0)))
                    except (TypeError, ValueError):
                        continue
                if vals:
                    derived[f"{col}_sum"] = round(sum(vals), 2)
                    derived[f"{col}_avg"] = round(sum(vals) / len(vals), 2)
        return derived


class Archiver:
    """把渲染产物落到本地（生产可换 S3/COS）."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or os.getenv(
            "DOC_PIPELINE_ARCHIVE_ROOT",
            str(Path.home() / ".agent-ops" / "documents"),
        ))
        self.root.mkdir(parents=True, exist_ok=True)

    def archive(self, template: str, content: str,
                fingerprint: str) -> str:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        sub = self.root / template / date
        sub.mkdir(parents=True, exist_ok=True)
        path = sub / f"{fingerprint[:12]}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)


class AuditTrail:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path or os.getenv(
            "DOC_PIPELINE_AUDIT_LOG",
            str(Path.home() / ".agent-ops" / "audit" / "pipeline.jsonl"),
        ))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []

    def log(self, **fields):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self.records.append(record)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record


# ────────────────── 主流水线 ──────────────────

class DocumentPipeline:
    """7 阶段文档流水线。

    用法:
        p = DocumentPipeline()
        result = p.run(template="incident_report", data={...})
    """

    def __init__(
        self,
        ingestor: Optional[Ingestor] = None,
        normalizer: Optional[Normalizer] = None,
        extractor: Optional[Extractor] = None,
        renderer: Optional[TemplateRenderer] = None,
        archiver: Optional[Archiver] = None,
        audit: Optional[AuditTrail] = None,
        distributor: Optional[Callable[[str, dict], Any]] = None,
        template_dir: Optional[Path] = None,
    ):
        self.ingestor = ingestor or Ingestor()
        self.normalizer = normalizer or Normalizer()
        self.extractor = extractor or Extractor()
        self.renderer = renderer or TemplateRenderer()
        self.archiver = archiver or Archiver()
        self.audit = audit or AuditTrail()
        self.distributor = distributor
        self.template_dir = Path(template_dir or TEMPLATE_DIR)

    def list_templates(self) -> list[str]:
        return sorted(p.stem.replace(".md", "")
                      for p in self.template_dir.glob("*.md.tpl"))

    def _load_template(self, name: str) -> str:
        path = self.template_dir / f"{name}.md.tpl"
        if not path.exists():
            available = ", ".join(self.list_templates())
            raise FileNotFoundError(
                f"template '{name}' not found in {self.template_dir}. "
                f"Available: {available}"
            )
        return path.read_text(encoding="utf-8")

    def run(
        self,
        template: str,
        data: Any,
        *,
        defaults: Optional[dict] = None,
        distribute: bool = False,
        archive: bool = True,
        extra_context: Optional[dict] = None,
    ) -> PipelineResult:
        stages: list[StageResult] = []
        trace_id = f"pl_{int(time.time() * 1000)}"

        # 1) Ingest
        t0 = time.time()
        try:
            raw = self.ingestor.ingest(data)
            stages.append(StageResult("ingest",
                                      int((time.time() - t0) * 1000), True,
                                      output_summary=f"{len(raw)} keys"))
        except Exception as e:                        # noqa: BLE001
            stages.append(StageResult("ingest",
                                      int((time.time() - t0) * 1000), False,
                                      error=str(e)))
            self.audit.log(stage="ingest", trace_id=trace_id, error=str(e))
            raise

        # 2) Normalize
        t0 = time.time()
        normed = self.normalizer.normalize(raw, defaults=defaults)
        stages.append(StageResult("normalize",
                                  int((time.time() - t0) * 1000), True))

        # 3) Extract
        t0 = time.time()
        extracted = self.extractor.extract(normed)
        if extra_context:
            extracted.update(extra_context)
        stages.append(StageResult("extract",
                                  int((time.time() - t0) * 1000), True))

        # 4) Render
        t0 = time.time()
        tpl = self._load_template(template)
        rendered = self.renderer.render(tpl, extracted)
        stages.append(StageResult("render",
                                  int((time.time() - t0) * 1000), True,
                                  output_summary=f"{len(rendered)} chars"))

        fingerprint = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

        # 5) Archive
        archive_path = None
        if archive:
            t0 = time.time()
            archive_path = self.archiver.archive(template, rendered,
                                                 fingerprint)
            stages.append(StageResult("archive",
                                      int((time.time() - t0) * 1000), True,
                                      output_summary=archive_path))

        # 6) Distribute
        distribute_result = None
        if distribute and self.distributor is not None:
            t0 = time.time()
            try:
                distribute_result = self.distributor(rendered, extracted)
                stages.append(StageResult("distribute",
                                          int((time.time() - t0) * 1000),
                                          True))
            except Exception as e:                    # noqa: BLE001
                stages.append(StageResult("distribute",
                                          int((time.time() - t0) * 1000),
                                          False, error=str(e)))

        # 7) Audit
        self.audit.log(
            stage="completed", trace_id=trace_id,
            template=template, fingerprint=fingerprint,
            archive_path=archive_path,
            stages=[
                {"stage": s.stage, "ok": s.ok, "duration_ms": s.duration_ms,
                 "error": s.error}
                for s in stages
            ],
        )

        return PipelineResult(
            template=template,
            rendered=rendered,
            fingerprint=fingerprint,
            archive_path=archive_path,
            stages=stages,
            distribute_result=distribute_result,
            audit_id=trace_id,
        )
