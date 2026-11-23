from __future__ import annotations

import argparse
import sys

from .config import Settings


def _ingest(s: Settings) -> None:
    from .rag.embeddings import OllamaEmbedder
    from .rag.retriever import ingest_directory
    from .rag.store import VectorStore

    store = VectorStore(OllamaEmbedder(s.embed_model, s.ollama_host), s.rag_collection, s.chroma_dir)
    n = ingest_directory(store, s.docs_dir, reset=True)
    print(f"Indexed {n} chunks from {s.docs_dir}")


def _chat(s: Settings) -> None:
    from .agent.graph import build_default_agent

    agent = build_default_agent(s)
    print(f"Model: {s.llm_model}. Type 'exit' to quit.\n")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        r = agent.ask(q, thread_id="cli")
        for c in r.tool_calls:
            print(f"  [tool] {c['name']}({c['args']})")
        print(f"bot> {r.answer}\n  ({r.elapsed_s:.1f}s)\n")


def _serve(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("industrial_ai.api.main:app", host=host, port=port)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="industrial_ai", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("command", choices=["ingest", "chat", "serve", "bench", "eval"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a, rest = p.parse_known_args(argv)
    s = Settings.from_env()
    if a.command == "ingest":
        _ingest(s)
    elif a.command == "chat":
        _chat(s)
    elif a.command == "serve":
        _serve(a.host, a.port)
    elif a.command == "bench":
        from .bench.cli import main as bench_main
        bench_main(rest)
    elif a.command == "eval":
        from .evals.cli import main as eval_main
        eval_main(rest)


if __name__ == "__main__":
    main()
