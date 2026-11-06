import asyncio
import os

from minimax_code import MCode, MCodeOptions, ThreadOptions, RunOptions
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode


# 1. Configure OTel to export traces to the console.
provider = TracerProvider(
    resource=Resource.create({"service.name": "minimax-demo"})
)

provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("minimax-demo")


async def main():
    print("OTel configured")

    # 2. Create a MiniMax client using the existing login in the container.
    client = MCode(
        MCodeOptions(bin=os.environ["MCODE_BIN"])
    )

    # 3. Start a new conversation.
    conversation = client.start_thread(
        ThreadOptions(
            cwd="/workspace",
            permission="smart",
        )
    )

    # 4. Start a span before the actual call and close it automatically afterward.
    with tracer.start_as_current_span(
        "minimax.chat",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
        },
    ) as span:
        print("Calling MiniMax...")

        turn = await conversation.run(
            "Hello, please introduce yourself in one sentence in English. There is no need to read files or execute commands.",
            RunOptions(
                timeout_ms=90000,
                max_steps=4,
            ),
        )

        span.set_status(Status(StatusCode.OK))

        print("\nMiniMax response:")
        print(turn.final_response)
        print("\nSession:", turn.session_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        provider.shutdown()