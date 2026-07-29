import argparse
import asyncio
import os
import sys
from datetime import datetime

from fastcontext.agent.agent_factory import make_fastcontext_agent
from fastcontext.agent.llm import LLMConfigError


def main():
    """FastContext Command Line Interface"""
    parser = argparse.ArgumentParser(
        description="FastContext CLI",
    )

    parser.add_argument("--query", "-q", type=str, help="query to ask the agent")
    parser.add_argument(
        "--traj",
        "-t",
        type=str,
        help="agent trajectory file",
        default=f".fastcontext/trajectory_{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jsonl",
    )
    parser.add_argument("--max-turns", type=int, help="maximum number of turns", default=4)
    parser.add_argument("--verbose", action="store_true", help="whether to run in verbose mode")
    parser.add_argument(
        "--citation",
        action="store_true",
        help="Return only the <final_answer> citation block; falls back to the full answer when none is emitted",
    )

    args = parser.parse_args()

    work_dir = os.getcwd()
    agent = make_fastcontext_agent(trajectory_file=args.traj, work_dir=work_dir)

    prompt = args.query
    try:
        final_output = asyncio.run(
            agent.run(prompt=prompt, max_turns=args.max_turns, verbose=args.verbose, citation=args.citation)
        )
    except LLMConfigError as e:
        # A misconfigured environment is the caller's mistake, not a result.
        # Exit non-zero so a script driving this notices.
        print(f"Configuration error: {e}", file=sys.stderr)
        raise SystemExit(2) from e
    print(final_output)


if __name__ == "__main__":
    main()
