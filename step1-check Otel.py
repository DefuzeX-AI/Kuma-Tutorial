from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

# observe Minimax
provider = TracerProvider(
    resource=Resource.create({"service.name": "minimax-demo"})
)


provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("minimax-demo")

print("OTel configured")
