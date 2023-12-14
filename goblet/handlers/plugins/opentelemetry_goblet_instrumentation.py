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

import logging
from typing import Collection

import flask
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


from goblet import Goblet

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
        trace_parent = request.headers.get("Traceparent")
        trace_context_header = request.headers.get("X-Cloud-Trace-Context")

        if trace_context_header:
            log.info(f"before_request X-Cloud-Trace-Context: {trace_context_header}")
            log.info(f"before_request Traceparent {trace_parent}")
            log.info(f"flask headers {flask.request.headers}")
            info = trace_context_header.split(";")[0].split("/")

            trace_id = info[0]
            span_id = info[1]

            log.info(f"{trace_id}/{span_id}")
            log.info(trace.get_current_span())
            log.info(trace.get_current_span().get_span_context())
            current_span = (
                trace.get_tracer(__name__).start_span(request.path)
                # .start_as_current_span(
                #     request.path,
                #     links=[
                #         Link(
                #             SpanContext(
                #                 trace_id=int(trace_id, 16),
                #                 span_id=int(span_id),
                #                 is_remote=True,
                #             )
                #         )
                #     ],
                # )
                # .__enter__()
            ).__enter__()

            log.info(f"before request span: {current_span}")
        return request

    def _instrument(self, app: Goblet):
        """Instrument the library"""
        app.before_request()(self._before_request)
        # app.after_request()(self._after_request)

    def instrument_app(self, app: Goblet):
        self.instrument(app=app)

    def _uninstrument(self, **kwargs):
        """Uninstrument the library"""
