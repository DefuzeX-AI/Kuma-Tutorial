import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from minimax_code import (
    MCode,
    MCodeOptions,
    ThreadOptions,
    RunOptions,
)

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode

from kuma import create_run, to_json, KumaError
from kuma.otel import configure_trace_evidence


# 1. Load .env from the script directory.
workspace = Path(__file__).resolve().parent
load_dotenv(workspace / ".env")

# 2. Configure OTel to keep exporting traces of actual calls to the console.
provider = TracerProvider(
    resource=Resource.create({"service.name": "minimax-demo"})
)
provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("minimax-demo")

# 3. Let KUMA capture traces from the same provider.
capture = configure_trace_evidence(provider)


async def main():
    # 4. Read requirement.md and use the official service to generate a case.
    # Omit case_provider / judge_provider to use the official generation and judging services.
    print("Requesting case generation from the official service based on requirement.md...")

    run = create_run(
        repo_path=workspace,
        agent_profile_path=workspace / "requirement.md",
        trace_evidence=capture,
        max_steps=1, # If None, defaults to at most 10 rounds; set to 1 if only one search round is supported.
        judge=True,
        save_local=True,
        operation_wait_timeout=600,
    )

    try:
        # 5. Save the complete case to .kuma.
        case_dir = workspace / ".kuma"
        case_dir.mkdir(exist_ok=True)

        case_path = run.save_case(
            f".kuma/case-{run.run_id}.json"
        )

        print("\nCase saved to:", case_path)


        # 6. Create a MiniMax client using the existing login in the container.
        # Exclude KUMA environment variables from the MiniMax subprocess.
        agent_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("KUMA_")
        }

        client = MCode(
            MCodeOptions(
                bin=os.environ["MCODE_BIN"],
                env=agent_env,
            )
        )

        # Create a new session for this case, preserving context across rounds.
        conversation = client.start_thread(
            ThreadOptions(
                cwd=str(workspace),
                permission="smart",
            )
        )

        # 7. Execute all rounds of the official case in order.
        round_number = 0

        while (item := run.get_input(full=True)) is not None:
            round_number += 1
            print(
                f"\n===== MiniMax executing round "
                f"{round_number}/{run.max_steps} ====="
            )

            # get_input has opened the evidence capture window for this round.
            # This span wraps the actual MiniMax call.
            with tracer.start_as_current_span(
                "minimax.chat",
                attributes={
                    "gen_ai.operation.name": "invoke_agent",
                },
            ) as span:
                turn = await conversation.run(
                    item.payload,
                    RunOptions(
                        timeout_ms=180000,
                        max_steps=16,
                    ),
                )

                span.set_status(Status(StatusCode.OK))

                print("\nMiniMax response:")
                print(turn.final_response)
                print("\nSession:", turn.session_id)

            # 8. After the span ends, submit this round's response and captured evidence.
            if round_number == run.max_steps:
                print("\nSubmitting the final round and waiting for the official judge...")
            else:
                print("\nSubmitting the results for this round...")

            try:
                run.submit(
                    turn.final_response,
                    status="completed",
                )

            except KumaError as exc:
                print("\nKUMA submission or judging failed:", str(exc))
                print("Error code:", exc.code)
                print("Retryable:", exc.retryable)
                print("Run ID:", run.run_id)
                print("Current run state:", run.state)
                print("Please keep the existing records in .kuma.")

                # Exit main without reading or saving a report that has not been generated.
                return

        # 9. After submitting all rounds, read the official judge report.
        report = run.report
        report_data = to_json(report)

        print("\n===== Official Judge Report =====")
        print("Verdict:", report.status)
        print("Confidence:", report.confidence)
        print(
            json.dumps(
                report_data,
                ensure_ascii=False,
                indent=2,
            )
        )

        # 10. Save the report to .kuma.
        report_path = (
            case_dir / f"report-{run.run_id}.json"
        )
        report_path.write_text(
            json.dumps(
                report_data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print("\nReport saved to:", report_path)

    finally:
        # Cancel any unfinished run when exiting early.
        if run.state in {"ready", "input_delivered"}:
            run.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        provider.shutdown()