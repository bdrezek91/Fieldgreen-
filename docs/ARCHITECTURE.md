# Architecture

The accepted PHASE 0 architecture is defined in
[`PHASE_0_ARCHITECTURE_RESEARCH.md`](PHASE_0_ARCHITECTURE_RESEARCH.md).

PHASE 1 establishes only the repository, tooling and safety boundary. The current package
contains settings and a network-disabled heartbeat. Domain contracts, data adapters,
backtesting, risk, portfolio and execution are intentionally not implemented yet.

Dependency rule: future domain code must not import exchange or backtesting framework types.
Adapters may depend on the domain, never the reverse.
