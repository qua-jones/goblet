"""
This library builds on the OpenTelemetry WSGI middleware to track web requests
in Goblet applications.

Usage
-----

.. code-block:: python

    from flask import Flask
    from goblet.resource.plugins.instrumentation.opentelemetry_goblet_instrumentation import GobletInstrumentor

    app = Goblet()

    GobletInstrumentor().instrument_app(app)

    @app.route("/")
    def hello():
        return "Hello!"
"""

from typing import Collection

from goblet import Goblet, Response


from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.trace.span import SpanContext, Span
from opentelemetry.trace import Link

import logging


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

tracer_provider = TracerProvider()
cloud_trace_exporter = CloudTraceSpanExporter()
tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))

prop = CloudTraceFormatPropagator()
carrier = {}


trace.set_tracer_provider(tracer_provider)


set_global_textmap(prop)


class GobletInstrumentor(BaseInstrumentor):
    # pylint: disable=protected-access,attribute-defined-outside-init
    """An instrumentor for Goblet"""

    def instrumentation_dependencies(self) -> Collection[str]:
        return ("goblet-gcp <= 1.0",)

    @staticmethod
    def _before_request(request):
        """
        X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=TRACE_TRUE
        """

        log.info(request.headers)
        log.info(request.headers.get("Traceparent"))
        trace_context_header = request.headers.get("X-Cloud-Trace-Context")

        if trace_context_header:
            log.info(trace_context_header)
            log.info(type(trace_context_header))

            info = trace_context_header.split(";")[0].split("/")

            trace_id = info[0]
            span_id = info[1]

        log.info(f"{trace_id}/{span_id}")
        trace.get_tracer(__name__).start_as_current_span(
            request.path,
            links=[
                Link(
                    SpanContext(
                        trace_id=int(trace_id, 16),
                        span_id=int(span_id),
                        is_remote=True,
                    )
                )
            ],
        ).__enter__()

        # else:
        #     trace.get_tracer(__name__).start_as_current_span(request.path).__enter__()
        prop.inject(carrier=carrier)
        return request

    @staticmethod
    def _after_request(response):
        log.info(response)
        log.info(type(response))

        current_span = trace.get_current_span()
        current_span_context = current_span.get_span_context()

        if not isinstance(response, Response):
            response = Response(response)

        log.info(response)
        log.info(response.headers)
        log.info(current_span)
        log.info(current_span_context)
        trace_context = (
            f"{current_span_context.trace_id}"  # /{current_span_context.span_id};o=1"
        )

        response.headers["X-Cloud-Trace-Context"] = trace_context
        log.info(response.headers)
        return response

    def _instrument(self, app: Goblet):
        """Instrument the library"""
        app.g.tracer = trace.get_tracer(__name__)
        app.g.prop = prop
        app.g.carrier = carrier
        app.before_request()(self._before_request)
        app.after_request()(self._after_request)

    def instrument_app(self, app: Goblet):
        self.instrument(app=app)

    def _uninstrument(self, **kwargs):
        """Uninstrument the library"""
