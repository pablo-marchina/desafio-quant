#!/usr/bin/env python3
"""Recuperação do Qdrant — recria o container com volume persistente, reseta o
flag is_embedded no PostgreSQL e re-roda os vetorizadores (Fase 2 + base NVIDIA).

Uso:
  python recover_qdrant.py --dry-run         # mostra o plano sem executar nada
  python recover_qdrant.py                   # recuperação completa
  python recover_qdrant.py --skip-docker     # assume que o Qdrant já está no ar
  python recover_qdrant.py --batch-size 32   # batch size customizado p/ vetorizador
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import time
from pathlib import Path

import asyncpg
from qdrant_client import AsyncQdrantClient

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging

setup_logging()
logger = get_logger("recover_qdrant")

ROOT = Path(__file__).parent
QDRANT_IMAGE = "qdrant/qdrant"
QDRANT_CONTAINER_NAME = "qdrant"
QDRANT_VOLUME = "qdrant_storage"
EXPECTED_COLLECTIONS = ["startup_chunks", "nvidia_tech_knowledge"]


# =============================================================================
# Docker
# =============================================================================

async def _run(*cmd: str, check: bool = True) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    text = out.decode(errors="replace").strip()
    if check and proc.returncode != 0:
        raise RuntimeError(f"Comando falhou ({' '.join(cmd)}): {text}")
    return proc.returncode, text


async def recreate_qdrant_container(dry_run: bool) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker não encontrado no PATH. Instale o Docker ou rode com --skip-docker "
            "se já tiver um Qdrant rodando manualmente."
        )

    returncode, names = await _run(
        "docker", "ps", "-a", "--filter", f"ancestor={QDRANT_IMAGE}", "--format", "{{.Names}}",
        check=False,
    )
    if returncode != 0:
        raise RuntimeError(
            f"Falha ao listar containers Docker: {names}. Verifique se o Docker está "
            "rodando e se seu usuário tem permissão (grupo 'docker') para usar o socket Docker."
        )
    existing = [n for n in names.splitlines() if n.strip()]

    if dry_run:
        for name in existing:
            print(f"  [dry-run] docker rm -f {name}")
        print(
            f"  [dry-run] docker run -d -p 6333:6333 --name {QDRANT_CONTAINER_NAME} "
            f"-v {QDRANT_VOLUME}:/qdrant/storage {QDRANT_IMAGE}"
        )
        return

    for name in existing:
        logger.info("Removendo container existente '%s' (imagem %s)...", name, QDRANT_IMAGE)
        await _run("docker", "rm", "-f", name)

    await _run(
        "docker", "run", "-d", "-p", "6333:6333", "--name", QDRANT_CONTAINER_NAME,
        "-v", f"{QDRANT_VOLUME}:/qdrant/storage", QDRANT_IMAGE,
    )
    logger.info("Container '%s' criado com volume persistente '%s'.", QDRANT_CONTAINER_NAME, QDRANT_VOLUME)


async def wait_for_qdrant(settings, timeout: float = 60.0) -> None:
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False)
    t0 = time.monotonic()
    last_exc: Exception | None = None
    try:
        while time.monotonic() - t0 < timeout:
            try:
                await client.get_collections()
                logger.info("Qdrant respondendo em %s:%d.", settings.qdrant_host, settings.qdrant_port)
                return
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(1.5)
    finally:
        await client.close()
    raise RuntimeError(
        f"Qdrant não respondeu em {settings.qdrant_host}:{settings.qdrant_port} "
        f"após {timeout:.0f}s. Último erro: {last_exc}"
    )


# =============================================================================
# PostgreSQL
# =============================================================================

async def reset_is_embedded(settings, dry_run: bool) -> int:
    if dry_run:
        print("  [dry-run] UPDATE startups_content SET is_embedded = FALSE;")
        return 0
    try:
        conn = await asyncpg.connect(dsn=settings.database_url)
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao conectar ao PostgreSQL: {exc}. "
            "Verifique se o serviço está rodando e se DATABASE_URL no .env está correto."
        ) from exc
    try:
        status = await conn.execute("UPDATE startups_content SET is_embedded = FALSE")
        return int(status.split()[-1])  # status no formato "UPDATE <n>"
    finally:
        await conn.close()


# =============================================================================
# Vetorizadores (subprocess com streaming de stdout em tempo real)
# =============================================================================

async def _run_script(*args: str, dry_run: bool) -> None:
    cmd = [sys.executable, *args]
    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        return

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        print(line.decode(errors="replace").rstrip())

    returncode = await proc.wait()
    if returncode != 0:
        raise RuntimeError(
            f"'{' '.join(cmd)}' terminou com código {returncode}. "
            "Veja o log acima e rode o comando manualmente para depurar."
        )


# =============================================================================
# Validação final
# =============================================================================

async def validate_collections(settings) -> dict[str, int]:
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False)
    try:
        existing = {c.name for c in (await client.get_collections()).collections}
        counts: dict[str, int] = {}
        for name in EXPECTED_COLLECTIONS:
            if name not in existing:
                raise RuntimeError(f"Coleção '{name}' não foi criada no Qdrant.")
            info = await client.get_collection(name)
            counts[name] = info.points_count or 0
            if counts[name] == 0:
                raise RuntimeError(f"Coleção '{name}' existe mas está vazia (0 pontos).")
        return counts
    finally:
        await client.close()


# =============================================================================
# CLI / Main
# =============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recupera o Qdrant após perda de dados: recria o container com volume "
                    "persistente, reseta is_embedded no PostgreSQL e re-roda os vetorizadores."
    )
    p.add_argument("--dry-run", action="store_true", help="Mostra o plano sem executar nada.")
    p.add_argument("--skip-docker", action="store_true", help="Pula a etapa de gerenciamento do Docker.")
    p.add_argument("--batch-size", type=int, default=None,
                   help="Batch size do phase2_vectorizer.py (padrão: EMBED_BATCH_SIZE).")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    batch_size = args.batch_size or settings.embed_batch_size
    t_start = time.monotonic()

    skip_note = "(pulado) " if args.skip_docker else ""
    print(f"🐳 [1/5] {skip_note}Recriando container Qdrant com persistência...")
    if not args.skip_docker:
        await recreate_qdrant_container(args.dry_run)
    if not args.dry_run:
        await wait_for_qdrant(settings)

    print("🐘 [2/5] Resetando flag is_embedded no PostgreSQL...")
    n_reset = await reset_is_embedded(settings, args.dry_run)
    if not args.dry_run:
        logger.info("%d linha(s) resetadas (is_embedded=FALSE).", n_reset)

    print(f"🔄 [3/5] Executando phase2_vectorizer.py (batch_size={batch_size})...")
    await _run_script(str(ROOT / "phase2_vectorizer.py"), "--batch-size", str(batch_size), dry_run=args.dry_run)

    print("🔄 [4/5] Executando ingest_nvidia_docs.py --force...")
    await _run_script(str(ROOT / "ingest_nvidia_docs.py"), "--force", dry_run=args.dry_run)

    print("✅ [5/5] Validando coleções no Qdrant...")
    if args.dry_run:
        print("  [dry-run] GET /collections (startup_chunks, nvidia_tech_knowledge)")
        print("\n[DRY-RUN] Nenhuma alteração foi feita.")
        return

    counts = await validate_collections(settings)
    elapsed = time.monotonic() - t_start
    minutes, seconds = divmod(int(elapsed), 60)

    print("\n🎉 Recuperação concluída com sucesso!")
    print("📊 Coleções no Qdrant:")
    for name, count in counts.items():
        print(f"   - {name}: {count} pontos")
    print(f"🕒 Tempo total: {minutes}m{seconds:02d}s")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        print(f"\n❌ Falha na recuperação: {exc}", file=sys.stderr)
        sys.exit(1)
