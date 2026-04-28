# Defines chaos profiles for CPU, memory, and network throttling.

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ResourceSnapshot:
    """
    One moment-in-time resource state.
    None = baseline to be used for comparisons
    """
    # CPU: fraction of one core (0.1 = 10%, 1.0 = full core)
    cpu_quota: Optional[float] = None
    cpu_period_us: int = 100_000       # 100ms window (Docker default)

    # Memory (MB). Set swap == memory to disable swap.
    memory_mb: Optional[int] = None
    memory_swap_mb: Optional[int] = None

    # Network (applied inside container via `tc`). Needs NET_ADMIN cap.
    # NEEDS FURTHER TESTING
    net_delay_ms:  Optional[int]   = None   # added latency per packet
    net_loss_pct:  Optional[float] = None   # packet loss percentage
    net_rate_kbps: Optional[int]   = None   # bandwidth cap in kbps

    def to_run_flags(self) -> list[str]:
        flags = []
        if self.cpu_quota is not None:
            flags += ["--cpus", str(self.cpu_quota)]
        if self.memory_mb is not None:
            flags += ["--memory", f"{self.memory_mb}m"]
            swap = self.memory_swap_mb if self.memory_swap_mb is not None else self.memory_mb
            flags += ["--memory-swap", f"{swap}m"]
        return flags

    def to_update_flags(self) -> list[str]:
        """
        Flags for `docker update` — must use --cpu-period/--cpu-quota,
        not --cpus (docker update doesn't support --cpus).
        On macOS/Docker Desktop these may not take effect due to the VM layer (Linux would be ideal).
        """
        flags = []
        if self.cpu_quota is not None:
            flags += ["--cpu-period", str(self.cpu_period_us),
                    "--cpu-quota",  str(int(self.cpu_quota * self.cpu_period_us))]
        if self.memory_mb is not None:
            flags += ["--memory", f"{self.memory_mb}m"]
            swap = self.memory_swap_mb if self.memory_swap_mb is not None else self.memory_mb
            flags += ["--memory-swap", f"{swap}m"]
        return flags

    def to_tc_commands(self) -> list[list[str]]:
        """
        Commands to exec INSIDE the container via `docker exec` to apply
        network chaos using Linux tc (traffic control).
        Always clears previous rules first.
        NEEDS FURTHER TESTING
        """
        cmds: list[list[str]] = []
        # Clear any existing qdisc; error if none exists is harmless
        cmds.append(["sh", "-c", "tc qdisc del dev eth0 root 2>/dev/null || true"])

        if not self.has_net_chaos():
            return cmds  # removes all network constraints

        # netem: handles delay + loss
        netem = "tc qdisc add dev eth0 root handle 1: netem"
        if self.net_delay_ms is not None:
            netem += f" delay {self.net_delay_ms}ms"
        if self.net_loss_pct is not None:
            netem += f" loss {self.net_loss_pct}%"
        cmds.append(["sh", "-c", netem])

        # tbf (token bucket filter): bandwidth cap, chained after netem
        if self.net_rate_kbps is not None:
            burst = max(self.net_rate_kbps * 125, 1600)  # bytes
            tbf = (
                f"tc qdisc add dev eth0 parent 1: handle 10: tbf "
                f"rate {self.net_rate_kbps}kbit burst {burst} latency 100ms"
            )
            cmds.append(["sh", "-c", tbf])

        return cmds

    def has_net_chaos(self) -> bool:
        return any(x is not None for x in
                   [self.net_delay_ms, self.net_loss_pct, self.net_rate_kbps])


@dataclass
# for runtime calcs
class DynamicStep:
    delay_s: float              # seconds after container start
    snapshot: ResourceSnapshot
    label: str = ""

@dataclass
class ChaosProfile:
    name: str
    description: str
    initial: ResourceSnapshot = field(default_factory=ResourceSnapshot)
    steps: list[DynamicStep] = field(default_factory=list)
    needs_net_admin: bool = False

    def __post_init__(self):
        all_snaps = [self.initial] + [s.snapshot for s in self.steps]
        self.needs_net_admin = any(s.has_net_chaos() for s in all_snaps)


PROFILES: dict[str, ChaosProfile] = {

    "none": ChaosProfile(
        name="none",
        description="clean baseline run",
    ),

   
    # MacOS docker VM won't allow for dynamic cpu manipulation, but these (in theory) should be able to run on Linux
    # Leaving because it might be cool to test eventually

    # "cpu_gradual": ChaosProfile(
    #     name="cpu_gradual",
    #     description="CPU steps down 100% → 50% → 25% → 10% every 5s",
    #     initial=ResourceSnapshot(cpu_quota=1.0),
    #     steps=[
    #         DynamicStep(5, ResourceSnapshot(cpu_quota=0.50), "CPU → 50%"),
    #         DynamicStep(10, ResourceSnapshot(cpu_quota=0.25), "CPU → 25%"),
    #         DynamicStep(15, ResourceSnapshot(cpu_quota=0.10), "CPU → 10%"),
    #     ],
    # ),

    # "cpu_spike": ChaosProfile(
    #     name="cpu_spike",
    #     description="CPU flaps between 100% and 5% every 4s (noisy neighbor simulation)",
    #     initial=ResourceSnapshot(cpu_quota=1.0),
    #     steps=[
    #         DynamicStep( 4, ResourceSnapshot(cpu_quota=0.05), "CPU → 5%  (starved)"),
    #         DynamicStep(8, ResourceSnapshot(cpu_quota=1.00), "CPU → 100% (restore)"),
    #         DynamicStep(12, ResourceSnapshot(cpu_quota=0.05), "CPU → 5%  (starved)"),
    #         DynamicStep(16, ResourceSnapshot(cpu_quota=1.00), "CPU → 100% (restore)"),
    #         DynamicStep(20, ResourceSnapshot(cpu_quota=0.05), "CPU → 5%  (starved)"),
    #     ],
    # ),

 # ── CPU ───────────────────────────────────────────────────────────────────
    "cpu_half": ChaosProfile(
        name="cpu_half",
        description="Fixed 50% CPU from start",
        initial=ResourceSnapshot(cpu_quota=0.5),
        steps=[],
    ),
    "cpu_tenth": ChaosProfile(
        name="cpu_tenth",
        description="Fixed 10% CPU from start (Severely throttle CPU)",
        initial=ResourceSnapshot(cpu_quota=0.1),
        steps=[],
    ),

    # ── Memory ────────────────────────────────────────────────────────────────
    "memory_squeeze": ChaosProfile(
        name="memory_squeeze",
        description="RAM shrinks 512→256→128→64→32 MB over 20s",
        initial=ResourceSnapshot(memory_mb=512, memory_swap_mb=512),
        steps=[
            DynamicStep(5, ResourceSnapshot(memory_mb=256, memory_swap_mb=256), "RAM → 256 MB"),
            DynamicStep(10, ResourceSnapshot(memory_mb=128, memory_swap_mb=128), "RAM → 128 MB"),
            DynamicStep(15, ResourceSnapshot(memory_mb=64,  memory_swap_mb=64),  "RAM → 64 MB"),
            DynamicStep(20, ResourceSnapshot(memory_mb=32,  memory_swap_mb=32),  "RAM → 32 MB (OOM risk)"),
        ],
    ),

    "memory_bomb": ChaosProfile(
        name="memory_bomb",
        description="Generous RAM, then sudden drop to 16 MB at 10s — tests OOM handling",
        initial=ResourceSnapshot(memory_mb=512, memory_swap_mb=512),
        steps=[
            DynamicStep(10, ResourceSnapshot(memory_mb=16, memory_swap_mb=16), "RAM → 16 MB"),
        ],
    ),

    "memory_ceiling": ChaosProfile(
        name="memory_ceiling",
        description="Fixed 256 MB ceiling from the start",
        initial=ResourceSnapshot(memory_mb=256, memory_swap_mb=256),
        steps=[],   # no dynamic changes
    ),

    # ── Network ───────────────────────────────────────────────────────────────
    # Largely untested ATM

    "network_degrade": ChaosProfile(
        name="network_degrade",
        description="Latency and loss ramp up, then bandwidth capped at 64kbps",
        initial=ResourceSnapshot(net_delay_ms=10),
        steps=[
            DynamicStep(5, ResourceSnapshot(net_delay_ms=150, net_loss_pct=2.0),  "net: 150ms + 2% loss"),
            DynamicStep(15, ResourceSnapshot(net_delay_ms=500, net_loss_pct=15.0), "net: 500ms + 15% loss"),
            DynamicStep(30, ResourceSnapshot(net_delay_ms=100, net_rate_kbps=64),  "net: 64kbps cap"),
        ],
    ),

    "network_flap": ChaosProfile(
        name="network_flap",
        description="100% packet loss every 5s to simulate intermittent outage",
        initial=ResourceSnapshot(),
        steps=[
            DynamicStep(5, ResourceSnapshot(net_loss_pct=100.0), "net: BLACKOUT"),
            DynamicStep(10, ResourceSnapshot(),                    "net: restore"),
            DynamicStep(15, ResourceSnapshot(net_loss_pct=100.0), "net: BLACKOUT"),
            DynamicStep(20, ResourceSnapshot(),                    "net: restore"),
        ],
    ),
}

def get_profile(name: str) -> ChaosProfile:
    if name not in PROFILES:
        raise ValueError(
            f"Unknown chaos profile '{name}'. Available: {', '.join(PROFILES)}"
        )
    return PROFILES[name]