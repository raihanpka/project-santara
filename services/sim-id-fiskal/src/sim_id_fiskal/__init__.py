"""sim-id-fiskal: Indonesian fiscal stress test service.

This is the first Santara service that actually answers a question.
It loads the public data from the Indonesia Fiscal Pressure Tracker
on the Hugging Face Hub and runs a transparent pass-through model
to estimate the inflation impact of a fuel price shock.
"""

from sim_id_fiskal.anchor import FiscalStressTest, StressResult

__all__ = ["FiscalStressTest", "StressResult"]
__version__ = "0.1.0"
