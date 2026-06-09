# SnowOS performance subsystem
import os
import sys

# Extend __path__ to include the runtime performance directory if it exists
runtime_perf = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../snowos-runtime/src/kernel_layer/performance'))
if os.path.isdir(runtime_perf):
    __path__.append(runtime_perf)
