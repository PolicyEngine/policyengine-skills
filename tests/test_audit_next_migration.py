from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_next_migration.py"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def run_audit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def test_audit_reports_next_migration_regressions(tmp_path: Path) -> None:
    write(
        tmp_path / "package.json",
        '{"dependencies":{"next":"16.2.6","react":"19.2.0"}}',
    )
    write(
        tmp_path / "next.config.mjs",
        'export default { basePath: "/us/example" };',
    )
    write(
        tmp_path / "vercel.json",
        '{"framework": null, "outputDirectory": "dist"}',
    )
    write(
        tmp_path / "app" / "layout.tsx",
        """
export const metadata = {
  icons: { icon: '/vite.svg' },
};
""",
    )
    write(
        tmp_path / "app" / "page.tsx",
        """
const DATA_URL = import.meta.env.VITE_DATA_URL;
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8501";
fetch(`/data/${DATA_URL}.json`);
axios.get('/api/example');
export default function Page() {
  return <img src="/logos/teal.svg" alt="" />;
}
""",
    )

    result = run_audit(tmp_path)

    assert result.returncode == 1
    assert "vite-env" in result.stderr
    assert "localhost-production-fallback" in result.stderr
    assert "basepath-root-fetch" in result.stderr
    assert "basepath-root-asset" in result.stderr
    assert "stale-vite-favicon" in result.stderr
    assert "vercel-next-dist-output" in result.stderr


def test_audit_allows_base_path_helpers(tmp_path: Path) -> None:
    write(
        tmp_path / "package.json",
        '{"dependencies":{"next":"16.2.6","react":"19.2.0"}}',
    )
    write(
        tmp_path / "next.config.mjs",
        'export default { basePath: "/us/example" };',
    )
    write(
        tmp_path / "vercel.json",
        '{"outputDirectory": "frontend/out"}',
    )
    write(tmp_path / "public" / "favicon.svg", "<svg></svg>")
    write(
        tmp_path / "app" / "layout.tsx",
        """
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
export const metadata = {
  icons: { icon: `${BASE_PATH}/favicon.svg` },
};
""",
    )
    write(
        tmp_path / "app" / "page.tsx",
        """
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
function assetPath(path) {
  return `${BASE_PATH}${path}`;
}
fetch(`${BASE_PATH}/data/results.json`);
if (process.env.NODE_ENV === "development") {
  const target = process.env.NEXT_PUBLIC_API_TARGET || "http://localhost:8000";
}
export default function Page() {
  return <img src={assetPath("/logos/teal.svg")} alt="" />;
}
""",
    )

    result = run_audit(tmp_path)

    assert result.returncode == 0
    assert "passed" in result.stdout


def test_audit_allows_base_path_image_wrapper(tmp_path: Path) -> None:
    write(
        tmp_path / "package.json",
        '{"dependencies":{"next":"16.2.6","react":"19.2.0"}}',
    )
    write(
        tmp_path / "next.config.ts",
        'export default { basePath: "/slides" };',
    )
    write(
        tmp_path / "components" / "Slide.tsx",
        """
import Image from '@/components/core/BasePathImage';

export function Slide() {
  return (
    <Image
      src="/logos/white.svg"
      alt=""
      width={100}
      height={40}
    />
  );
}
""",
    )

    result = run_audit(tmp_path)

    assert result.returncode == 0
